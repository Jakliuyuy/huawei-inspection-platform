"""基于现有可靠巡检脚本生成动态 SecureCRT VBScript。"""
from __future__ import annotations

import hashlib
from typing import Any

DIGEST_PLACEHOLDER = "__CANONICAL_SCRIPT_SHA256__"


def vb(value: object) -> str:
    return '"' + str(value).replace('"', '""').replace("\r", "").replace("\n", "") + '"'


def canonical_digest(script: str) -> str:
    canonical = script.replace(_embedded_digest(script), DIGEST_PLACEHOLDER)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _embedded_digest(script: str) -> str:
    marker = 'Const SCRIPT_SHA256 = "'
    start = script.find(marker)
    if start < 0:
        return DIGEST_PLACEHOLDER
    start += len(marker)
    end = script.find('"', start)
    return script[start:end] if end >= 0 else DIGEST_PLACEHOLDER


def generate_vbs(system_key: str, version: int, snapshot: dict[str, Any]) -> tuple[str, str]:
    lines = [_header(system_key, version)]
    for device in snapshot["devices"]:
        commands = ";;".join(f"{command['timeout_seconds']}|{command['command']}" for command in device["commands"])
        lines.append(
            f"    AddDevice devices, {vb(device['name'])}, {vb(device.get('ip', ''))}, "
            f"{vb(device.get('driver', 'huawei_vrp'))}, {vb(commands)}"
        )
    lines.append(_body())
    placeholder_script = "\r\n".join(lines)
    digest = hashlib.sha256(placeholder_script.encode("utf-8")).hexdigest()
    return placeholder_script.replace(DIGEST_PLACEHOLDER, digest), digest


def _header(system_key: str, version: int) -> str:
    return f'''\' $language = "VBScript"
' $interface = "1.0"
Option Explicit
Const ForWriting = 2
Const ForAppending = 8
Const SYSTEM_KEY = "{system_key}"
Const SYSTEM_VERSION = {version}
Const SCRIPT_SHA256 = "{DIGEST_PLACEHOLDER}"

Sub Main()
    Dim fso, root, manifest, summaryPath, summaryStream, devices, matchedDevices
    Dim i, key, d, runStamp, tabObj
    Set fso = CreateObject("Scripting.FileSystemObject")
    root = BuildLogRoot(fso)
    EnsureFolder fso, root
    manifest = fso.BuildPath(root, "inspection-manifest.tsv")
    runStamp = TimeStampForFile(Now)
    summaryPath = fso.BuildPath(root, SYSTEM_KEY & "_summary_" & runStamp & ".log")
    Set summaryStream = fso.OpenTextFile(summaryPath, ForWriting, True)
    Set devices = CreateObject("Scripting.Dictionary")
    Set matchedDevices = CreateObject("Scripting.Dictionary")'''


def _body() -> str:
    return '''    WriteManifestHeader fso, manifest
    summaryStream.WriteLine SYSTEM_KEY & " inspection started: " & Now
    summaryStream.WriteLine "Log directory: " & root
    summaryStream.WriteLine String(72, "=")
    If crt.GetTabCount() <= 0 Then
        summaryStream.WriteLine "No open tab found."
        summaryStream.Close
        crt.Dialog.MessageBox "No open tab found.", SYSTEM_KEY
        Exit Sub
    End If
    For i = 1 To crt.GetTabCount()
        Set tabObj = crt.GetTab(i)
        If Not tabObj Is Nothing Then
            ProcessTab fso, tabObj, root, manifest, summaryStream, devices, matchedDevices
        End If
    Next
    For Each key In devices.Keys
        If Not matchedDevices.Exists(CStr(key)) Then
            d = devices(key)
            WriteDeviceError fso, manifest, d, "device_not_connected", ""
            summaryStream.WriteLine "[" & Now & "] Device not connected or not matched: " & d(0) & " (" & d(1) & ")"
        End If
    Next
    summaryStream.WriteLine String(72, "=")
    summaryStream.WriteLine SYSTEM_KEY & " inspection finished: " & Now
    summaryStream.Close
    crt.Dialog.MessageBox "Inspection finished. Log directory:" & vbCrLf & root, SYSTEM_KEY
End Sub

Sub AddDevice(ByRef devices, ByVal name, ByVal ip, ByVal driver, ByVal commands)
    devices.Add CStr(devices.Count), Array(name, ip, driver, commands)
End Sub

Sub ProcessTab(ByRef fso, ByRef tabObj, ByVal root, ByVal manifest, ByRef summaryStream, ByRef devices, ByRef matchedDevices)
    Dim screenObj, caption, host, prompt, matchedKey, d, commandItems, item, fields
    Dim logPath, commandIndex, status, promptMatch
    If Not IsTabConnected(tabObj) Then
        summaryStream.WriteLine "[" & Now & "] Tab not connected, skip: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If
    Set screenObj = tabObj.Screen
    screenObj.Synchronous = True
    tabObj.Activate
    If HasVisiblePasswordDecisionPrompt(screenObj) Then
        SendPasswordDecisionNo screenObj
    Else
        screenObj.Send vbCr
    End If
    promptMatch = WaitForLoginPrompt(screenObj, 10)
    If promptMatch = 0 Then
        summaryStream.WriteLine "[" & Now & "] Prompt not detected, skip: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If
    prompt = CurrentPrompt(screenObj)
    caption = GetTabCaptionSafe(tabObj)
    host = GetSessionHostSafe(tabObj)
    matchedKey = ResolveDeviceKey(devices, caption & " " & host & " " & prompt)
    If matchedKey = "__AMBIGUOUS__" Then
        summaryStream.WriteLine "[" & Now & "] Ambiguous device match, skip tab: " & caption
        Exit Sub
    End If
    If Len(matchedKey) = 0 Then
        summaryStream.WriteLine "[" & Now & "] Device not configured, skip tab: " & caption & " prompt: " & prompt
        Exit Sub
    End If
    d = devices(matchedKey)
    If matchedDevices.Exists(matchedKey) Then
        WriteDeviceError fso, manifest, d, "duplicate_device", ""
        summaryStream.WriteLine "[" & Now & "] Duplicate device tab skipped: " & d(0)
        Exit Sub
    End If
    matchedDevices.Add matchedKey, True
    logPath = fso.BuildPath(root, SYSTEM_KEY & "_" & SafeName(d(0)) & "_" & TimeStampForFile(Now) & ".log")
    If Not StartSessionLog(tabObj, logPath) Then
        WriteDeviceError fso, manifest, d, "logging_failed", logPath
        summaryStream.WriteLine "[" & Now & "] Logging failed: " & d(0) & " path: " & logPath
        Exit Sub
    End If
    summaryStream.WriteLine "[" & Now & "] Start device: " & d(0) & " prompt: " & prompt
    SendCommandAndWait screenObj, prompt, "screen-length 0 temporary", 10, 1
    commandItems = Split(d(3), ";;")
    commandIndex = 0
    For Each item In commandItems
        commandIndex = commandIndex + 1
        fields = Split(item, "|", 2)
        status = "timeout"
        summaryStream.WriteLine "[" & Now & "] " & d(0) & " run command: " & fields(1)
        If SendCommandAndWait(screenObj, prompt, fields(1), CInt(fields(0)), 3) Then status = "success"
        AppendManifest fso, manifest, d(0), d(1), logPath, commandIndex, fields(1), CInt(fields(0)), status
    Next
    StopSessionLog tabObj
    summaryStream.WriteLine "[" & Now & "] Device finished: " & d(0) & " log: " & logPath
    summaryStream.WriteLine String(72, "-")
End Sub

Sub SendPasswordDecisionNo(ByRef screenObj)
    crt.Sleep 200
    screenObj.Send "N"
    crt.Sleep 100
    screenObj.Send "O"
    crt.Sleep 100
    screenObj.Send vbCr
End Sub

Function HasVisiblePasswordDecisionPrompt(ByRef screenObj)
    Dim screenText, startRow
    HasVisiblePasswordDecisionPrompt = False
    On Error Resume Next
    startRow = screenObj.CurrentRow - 4
    If startRow < 1 Then startRow = 1
    screenText = screenObj.Get(startRow, 1, screenObj.CurrentRow, screenObj.Columns)
    If Err.Number = 0 Then
        If (InStr(1, screenText, "Continue?", vbTextCompare) > 0 Or _
            InStr(1, screenText, "Change now?", vbTextCompare) > 0 Or _
            InStr(1, screenText, "Please choose", vbTextCompare) > 0) And _
           (InStr(1, screenText, "password", vbTextCompare) > 0 Or _
            InStr(1, screenText, "Please choose", vbTextCompare) > 0) Then
            HasVisiblePasswordDecisionPrompt = True
        End If
    End If
    Err.Clear
    On Error GoTo 0
End Function

Function WaitForLoginPrompt(ByRef screenObj, ByVal timeoutSeconds)
    Dim waitTexts, matchIndex, rowText, decisionCount
    waitTexts = Array("[Y/N]:", ">", "]", "#")
    decisionCount = 0
    WaitForLoginPrompt = 0
    On Error Resume Next
    Do
        matchIndex = screenObj.WaitForStrings(waitTexts, timeoutSeconds)
        If Err.Number <> 0 Or matchIndex = 0 Then Exit Function
        rowText = Trim(screenObj.Get(screenObj.CurrentRow, 1, screenObj.CurrentRow, screenObj.Columns))
        If matchIndex = 1 Or InStr(1, rowText, "[Y/N]", vbTextCompare) > 0 Then
            decisionCount = decisionCount + 1
            If decisionCount > 3 Then Exit Function
            SendPasswordDecisionNo screenObj
        Else
            WaitForLoginPrompt = matchIndex
            Exit Function
        End If
    Loop
End Function

Function SendCommandAndWait(ByRef screenObj, ByVal prompt, ByVal commandText, ByVal timeoutSeconds, ByVal maxContinuousTimeout)
    screenObj.Send commandText & vbCr
    SendCommandAndWait = WaitForPromptOrHandleMore(screenObj, prompt, timeoutSeconds, maxContinuousTimeout)
End Function

Function WaitForPromptOrHandleMore(ByRef screenObj, ByVal prompt, ByVal timeoutSeconds, ByVal maxContinuousTimeout)
    Dim waitTexts, matchIndex, timeoutCount
    If Len(prompt) > 0 Then
        waitTexts = Array("---- More ----", "---- More ( Press 'Q' to break ) ----", "--More--", prompt)
    Else
        waitTexts = Array("---- More ----", "---- More ( Press 'Q' to break ) ----", "--More--", ">", "]", "#")
    End If
    timeoutCount = 0
    Do
        matchIndex = screenObj.WaitForStrings(waitTexts, timeoutSeconds)
        If matchIndex = 0 Then
            timeoutCount = timeoutCount + 1
            If timeoutCount >= maxContinuousTimeout Then
                WaitForPromptOrHandleMore = False
                Exit Function
            End If
            screenObj.SendSpecial "MENU_SEND_BREAK"
        ElseIf matchIndex >= 1 And matchIndex <= 3 Then
            timeoutCount = 0
            screenObj.Send " "
        Else
            WaitForPromptOrHandleMore = True
            Exit Function
        End If
    Loop
End Function

Sub WriteManifestHeader(ByRef fso, ByVal path)
    Dim stream
    Set stream = fso.OpenTextFile(path, ForWriting, True)
    stream.WriteLine "system_key" & vbTab & "system_version" & vbTab & "script_sha256" & vbTab & "device_name" & vbTab & "ip" & vbTab & "log_file" & vbTab & "command_index" & vbTab & "command" & vbTab & "timeout_seconds" & vbTab & "status"
    stream.Close
End Sub

Sub AppendManifest(ByRef fso, ByVal path, ByVal name, ByVal ip, ByVal logPath, ByVal idx, ByVal command, ByVal timeoutSec, ByVal status)
    Dim stream, logName
    logName = ""
    If Len(logPath) > 0 Then logName = fso.GetFileName(logPath)
    Set stream = fso.OpenTextFile(path, ForAppending, True)
    stream.WriteLine SYSTEM_KEY & vbTab & SYSTEM_VERSION & vbTab & SCRIPT_SHA256 & vbTab & name & vbTab & ip & vbTab & logName & vbTab & idx & vbTab & command & vbTab & timeoutSec & vbTab & status
    stream.Close
End Sub

Sub WriteDeviceError(ByRef fso, ByVal path, ByRef d, ByVal status, ByVal logPath)
    AppendManifest fso, path, d(0), d(1), logPath, 0, "", 0, status
End Sub

Function ResolveDeviceKey(ByRef devices, ByVal haystack)
    Dim key, d, found
    found = ""
    For Each key In devices.Keys
        d = devices(key)
        If MatchesDevice(haystack, d(0), d(1)) Then
            If Len(found) > 0 Then
                ResolveDeviceKey = "__AMBIGUOUS__"
                Exit Function
            End If
            found = CStr(key)
        End If
    Next
    ResolveDeviceKey = found
End Function

Function MatchesDevice(ByVal haystack, ByVal name, ByVal ip)
    Dim aliasName
    MatchesDevice = (Len(name) > 0 And InStr(1, haystack, name, vbTextCompare) > 0) Or _
        (Len(ip) > 0 And InStr(1, haystack, ip, vbTextCompare) > 0)
    If MatchesDevice Then Exit Function
    aliasName = DeviceAlias(name)
    MatchesDevice = Len(aliasName) >= 8 And InStr(1, haystack, aliasName, vbTextCompare) > 0
End Function

Function DeviceAlias(ByVal name)
    Dim separator
    separator = InStr(1, name, "-", vbTextCompare)
    If separator > 0 Then DeviceAlias = Mid(name, separator + 1) Else DeviceAlias = ""
End Function

Function CurrentPrompt(ByRef screenObj)
    CurrentPrompt = ""
    On Error Resume Next
    CurrentPrompt = Trim(screenObj.Get(screenObj.CurrentRow, 1, screenObj.CurrentRow, screenObj.Columns))
    Err.Clear
    On Error GoTo 0
End Function

Function StartSessionLog(ByRef tabObj, ByVal logPath)
    StartSessionLog = False
    On Error Resume Next
    If tabObj.Session.Logging Then tabObj.Session.Log False
    Err.Clear
    tabObj.Session.LogFileName = logPath
    tabObj.Session.Log True
    If Err.Number = 0 And tabObj.Session.Logging Then StartSessionLog = True
    Err.Clear
    On Error GoTo 0
End Function

Sub StopSessionLog(ByRef tabObj)
    On Error Resume Next
    If tabObj.Session.Logging Then tabObj.Session.Log False
    Err.Clear
    On Error GoTo 0
End Sub

Function IsTabConnected(ByRef tabObj)
    IsTabConnected = False
    On Error Resume Next
    If Not tabObj Is Nothing Then IsTabConnected = tabObj.Session.Connected
    If Err.Number <> 0 Then IsTabConnected = False
    Err.Clear
    On Error GoTo 0
End Function

Function GetTabCaptionSafe(ByRef tabObj)
    GetTabCaptionSafe = ""
    On Error Resume Next
    If Not tabObj Is Nothing Then GetTabCaptionSafe = tabObj.Caption
    Err.Clear
    On Error GoTo 0
End Function

Function GetSessionHostSafe(ByRef tabObj)
    GetSessionHostSafe = ""
    On Error Resume Next
    GetSessionHostSafe = tabObj.Session.Config.GetOption("Hostname")
    Err.Clear
    On Error GoTo 0
End Function

Function SafeName(ByVal value)
    Dim chars, character
    chars = Array("\\", "/", ":", "*", "?", Chr(34), "<", ">", "|", " ")
    For Each character In chars
        value = Replace(value, character, "_")
    Next
    SafeName = value
End Function

Function DateFolder(ByVal value)
    DateFolder = Year(value) & "-" & Month(value) & "-" & Day(value)
End Function

Function TimeStampForFile(ByVal value)
    TimeStampForFile = Year(value) & Right("0" & Month(value), 2) & Right("0" & Day(value), 2) & "_" & _
        Right("0" & Hour(value), 2) & Right("0" & Minute(value), 2) & Right("0" & Second(value), 2)
End Function

Function BuildLogRoot(ByRef fso)
    Dim basePath, logsPath, datePath
    basePath = fso.GetParentFolderName(crt.ScriptFullName)
    logsPath = fso.BuildPath(basePath, "logs")
    datePath = fso.BuildPath(logsPath, DateFolder(Date))
    BuildLogRoot = fso.BuildPath(datePath, SYSTEM_KEY)
End Function

Sub EnsureFolder(ByRef fso, ByVal path)
    If fso.FolderExists(path) Then Exit Sub
    EnsureFolder fso, fso.GetParentFolderName(path)
    fso.CreateFolder path
End Sub'''
