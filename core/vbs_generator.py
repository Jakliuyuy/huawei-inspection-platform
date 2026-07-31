"""生成仅执行只读命令的 SecureCRT VBScript。"""
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
    if start < 0: return DIGEST_PLACEHOLDER
    start += len(marker); end = script.find('"', start)
    return script[start:end] if end >= 0 else DIGEST_PLACEHOLDER

def generate_vbs(system_key: str, version: int, snapshot: dict[str, Any]) -> tuple[str, str]:
    lines = [_header(system_key, version)]
    for device in snapshot["devices"]:
        commands = ";;".join(f"{c['timeout_seconds']}|{c['command']}" for c in device["commands"])
        lines.append(f"    AddDevice devices, {vb(device['name'])}, {vb(device.get('ip',''))}, {vb(device.get('driver','huawei_vrp'))}, {vb(commands)}")
    lines.append(_body(system_key, version))
    placeholder_script = "\r\n".join(lines)
    digest = hashlib.sha256(placeholder_script.encode("utf-8")).hexdigest()
    return placeholder_script.replace(DIGEST_PLACEHOLDER, digest), digest

def _header(system_key: str, version: int) -> str:
    return f'''' $language = "VBScript"
' $interface = "1.0"
Option Explicit
Const ForWriting = 2
Const ForAppending = 8
Const SYSTEM_KEY = "{system_key}"
Const SYSTEM_VERSION = {version}
Const SCRIPT_SHA256 = "{DIGEST_PLACEHOLDER}"

Sub Main()
    Dim fso, root, manifest, devices, matchedDevices, i, key, d
    Set fso = CreateObject("Scripting.FileSystemObject")
    root = fso.BuildPath(fso.GetParentFolderName(crt.ScriptFullName), SYSTEM_KEY & Chr(92) & DateFolder(Date))
    EnsureFolder fso, root
    manifest = fso.BuildPath(root, "inspection-manifest.tsv")
    Set devices = CreateObject("Scripting.Dictionary")
    Set matchedDevices = CreateObject("Scripting.Dictionary")'''

def _body(system_key: str, version: int) -> str:
    return '''    WriteManifestHeader fso, manifest
    For i = 1 To crt.GetTabCount()
        ProcessTab fso, crt.GetTab(i), root, manifest, devices, matchedDevices
    Next
    For Each key In devices.Keys
        If Not matchedDevices.Exists(CStr(key)) Then
            d = devices(key)
            WriteDeviceError fso, manifest, d, "device_not_connected", ""
        End If
    Next
    crt.Dialog.MessageBox "巡检完成：" & root, SYSTEM_KEY
End Sub

Sub AddDevice(ByRef devices, ByVal name, ByVal ip, ByVal driver, ByVal commands)
    devices.Add CStr(devices.Count), Array(name, ip, driver, commands)
End Sub

Sub ProcessTab(ByRef fso, ByRef tabObj, ByVal root, ByVal manifest, ByRef devices, ByRef matchedDevices)
    Dim caption, host, prompt, key, matchedKey, d, commandItems, item, fields, logPath
    If tabObj Is Nothing Then Exit Sub
    If Not tabObj.Session.Connected Then Exit Sub
    caption = tabObj.Caption : host = "" : On Error Resume Next
    host = tabObj.Session.Config.GetOption("Hostname") : On Error GoTo 0
    prompt = CurrentPrompt(tabObj.Screen) : matchedKey = ""
    For Each key In devices.Keys
        d = devices(key)
        If MatchesDevice(caption & " " & host & " " & prompt, d(0), d(1)) Then
            If Len(matchedKey) > 0 Then
                WriteDeviceError fso, manifest, d, "ambiguous_device", ""
                Exit Sub
            End If
            matchedKey = CStr(key)
        End If
    Next
    If Len(matchedKey) = 0 Then Exit Sub
    d = devices(matchedKey)
    If matchedDevices.Exists(matchedKey) Then
        WriteDeviceError fso, manifest, d, "duplicate_device", ""
        Exit Sub
    End If
    matchedDevices.Add matchedKey, True
    logPath = fso.BuildPath(root, SafeName(d(0)) & "_" & SafeName(d(1)) & ".log")
    On Error Resume Next
    Err.Clear : tabObj.Session.LogFileName = logPath : tabObj.Session.Log True, True
    If Err.Number <> 0 Or Not tabObj.Session.Logging Then
        Err.Clear : On Error GoTo 0
        WriteDeviceError fso, manifest, d, "logging_failed", logPath
        Exit Sub
    End If
    On Error GoTo 0
    commandItems = Split(d(3), ";;")
    Dim commandIndex : commandIndex = 0
    For Each item In commandItems
        commandIndex = commandIndex + 1 : fields = Split(item, "|", 2)
        RunCommand fso, manifest, tabObj.Screen, d, commandIndex, fields(1), CInt(fields(0)), logPath
    Next
    tabObj.Session.Log False
End Sub

Sub RunCommand(ByRef fso, ByVal manifest, ByRef screen, ByRef d, ByVal idx, ByVal command, ByVal timeoutSec, ByVal logPath)
    Dim status, matched
    status = "timeout" : screen.Synchronous = True : screen.Send command & vbCr
    matched = screen.WaitForStrings(Array(">", "#", "]"), timeoutSec)
    If matched > 0 Then status = "success"
    AppendManifest fso, manifest, d(0), d(1), logPath, idx, command, timeoutSec, status
End Sub

Sub WriteManifestHeader(ByRef fso, ByVal path)
    Dim s : Set s = fso.OpenTextFile(path, ForWriting, True)
    s.WriteLine "system_key" & vbTab & "system_version" & vbTab & "script_sha256" & vbTab & "device_name" & vbTab & "ip" & vbTab & "log_file" & vbTab & "command_index" & vbTab & "command" & vbTab & "timeout_seconds" & vbTab & "status"
    s.Close
End Sub

Sub AppendManifest(ByRef fso, ByVal path, ByVal name, ByVal ip, ByVal logPath, ByVal idx, ByVal command, ByVal timeoutSec, ByVal status)
    Dim s : Set s = fso.OpenTextFile(path, ForAppending, True)
    s.WriteLine SYSTEM_KEY & vbTab & SYSTEM_VERSION & vbTab & SCRIPT_SHA256 & vbTab & name & vbTab & ip & vbTab & fso.GetFileName(logPath) & vbTab & idx & vbTab & command & vbTab & timeoutSec & vbTab & status
    s.Close
End Sub

Sub WriteDeviceError(ByRef fso, ByVal path, ByRef d, ByVal status, ByVal logPath)
    AppendManifest fso, path, d(0), d(1), logPath, 0, "", 0, status
End Sub

Function MatchesDevice(ByVal haystack, ByVal name, ByVal ip)
    Dim aliasName
    MatchesDevice = (Len(name) > 0 And InStr(1, haystack, name, vbTextCompare) > 0) Or (Len(ip) > 0 And InStr(1, haystack, ip, vbTextCompare) > 0)
    If MatchesDevice Then Exit Function
    aliasName = DeviceAlias(name)
    MatchesDevice = Len(aliasName) >= 8 And InStr(1, haystack, aliasName, vbTextCompare) > 0
End Function

Function DeviceAlias(ByVal name)
    Dim separator : separator = InStr(1, name, "-", vbTextCompare)
    If separator > 0 Then DeviceAlias = Mid(name, separator + 1) Else DeviceAlias = ""
End Function

Function CurrentPrompt(ByRef screen)
    Dim startRow : startRow = screen.CurrentRow - 5
    If startRow < 1 Then startRow = 1
    On Error Resume Next : CurrentPrompt = Trim(screen.Get(startRow, 1, screen.CurrentRow, screen.Columns)) : On Error GoTo 0
End Function

Function SafeName(ByVal value)
    Dim chars, c : chars = Array("\\", "/", ":", "*", "?", Chr(34), "<", ">", "|", " ")
    For Each c In chars : value = Replace(value, c, "_") : Next : SafeName = value
End Function

Function DateFolder(ByVal value)
    DateFolder = Year(value) & "-" & Right("0" & Month(value), 2) & "-" & Right("0" & Day(value), 2)
End Function

Sub EnsureFolder(ByRef fso, ByVal path)
    If fso.FolderExists(path) Then Exit Sub
    EnsureFolder fso, fso.GetParentFolderName(path) : fso.CreateFolder path
End Sub'''
