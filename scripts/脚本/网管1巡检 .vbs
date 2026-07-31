' $language = "VBScript"
' $interface = "1.0"

Option Explicit

Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

Dim g_fso
Dim g_seenDevices
Set g_fso = CreateObject("Scripting.FileSystemObject")
Set g_seenDevices = CreateObject("Scripting.Dictionary")

Sub Main()
    Dim tabCount, logRoot, summaryPath, summaryStream
    Dim i, tabObj, runStamp

    logRoot = BuildLogRoot()
    EnsureFolderExists logRoot

    runStamp = TimeStampForFile(Now)
    summaryPath = g_fso.BuildPath(logRoot, "NM1_summary_" & runStamp & ".log")
    Set summaryStream = g_fso.OpenTextFile(summaryPath, ForWriting, True)
    summaryStream.WriteLine "NetMgmt-1 daily check started: " & Now
    summaryStream.WriteLine "Log directory: " & logRoot
    summaryStream.WriteLine String(72, "=")

    crt.Screen.Synchronous = True
    g_seenDevices.RemoveAll

    tabCount = crt.GetTabCount()
    If tabCount <= 0 Then
        summaryStream.WriteLine "No open tab found."
        summaryStream.Close
        crt.Dialog.MessageBox "No open tab found.", "SecureCRT Daily Check"
        Exit Sub
    End If

    For i = 1 To tabCount
        Set tabObj = crt.GetTab(i)
        If Not tabObj Is Nothing Then
            RunCheckForTab tabObj, logRoot, summaryStream, i
        End If
    Next

    summaryStream.WriteLine String(72, "=")
    summaryStream.WriteLine "NetMgmt-1 daily check finished: " & Now
    summaryStream.Close

    crt.Dialog.MessageBox "Daily check finished. Log directory:" & vbCrLf & logRoot, "SecureCRT Daily Check"
End Sub

Sub RunCheckForTab(ByRef tabObj, ByVal logRoot, ByRef summaryStream, ByVal tabIndex)
    Dim screenObj, logPath, commandList
    Dim prompt, disablePagerCmd
    Dim index, commandText, deviceName, matchIdx

    If Not IsTabConnected(tabObj) Then
        summaryStream.WriteLine "[" & Now & "] Tab not connected, skip caption: " & GetTabCaptionSafe(tabObj)
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
    
    ' Try to detect any common prompt, but do NOT skip if failed
    matchIdx = WaitForLoginPrompt(screenObj, 10)
    If matchIdx = 0 Then
        ' One more try with a short wait
        screenObj.Send vbCr
        matchIdx = WaitForLoginPrompt(screenObj, 5)
    End If

    Dim curRow, curLine
    If matchIdx > 0 Then
        curRow = screenObj.CurrentRow
        curLine = Trim(screenObj.Get(curRow, 1, curRow, screenObj.Columns))
        prompt = curLine
    Else
        ' Could not detect prompt, use a fallback prompt set for 'more' handling
        prompt = ""
        summaryStream.WriteLine "[" & Now & "] Warn: No exact prompt captured, using fallback."
    End If

    ' Device name extraction (fallback to tab index)
    deviceName = ExtractDeviceNameFromText(GetTabCaptionSafe(tabObj))
    If Len(deviceName) = 0 Then
        deviceName = ExtractDeviceNameFromPrompt(prompt)
    End If
    If Len(deviceName) = 0 Then
        deviceName = "Tab" & tabIndex
    End If
    deviceName = SanitizeFileName(deviceName)
    
    ' Avoid processing same device twice
    If g_seenDevices.Exists(deviceName) Then
        summaryStream.WriteLine "[" & Now & "] Device already processed, skip duplicate: " & deviceName
        Exit Sub
    End If
    g_seenDevices.Add deviceName, True

    summaryStream.WriteLine "[" & Now & "] Start tab: " & deviceName & " (prompt=" & prompt & ")"

    logPath = g_fso.BuildPath(logRoot, "NM1_" & deviceName & "_" & TimeStampForFile(Now) & ".log")
    If Not StartSessionLog(tabObj, logPath) Then
        summaryStream.WriteLine "[" & Now & "] Failed to start session log for " & deviceName & ", skip."
        Exit Sub
    End If

    ' Attempt to disable paging (Huawei/H3C), ignore errors
    disablePagerCmd = "screen-length 0 temporary"
    summaryStream.WriteLine "[" & Now & "] Sending pager off command..."
    If prompt <> "" Then
        SendCommandAndWait screenObj, prompt, disablePagerCmd, 10, 1
    Else
        screenObj.Send disablePagerCmd & vbCr
        crt.Sleep 2000
    End If

    commandList = GetCommandsForSession(deviceName)
    For index = 0 To UBound(commandList)
        commandText = commandList(index)
        If Len(Trim(commandText)) > 0 Then
            summaryStream.WriteLine "[" & Now & "] " & deviceName & " running: " & commandText
            If Not SendCommandAndWait(screenObj, prompt, commandText, 120, 3) Then
                summaryStream.WriteLine "[" & Now & "] " & deviceName & " command may have timed out: " & commandText
            End If
        End If
    Next

    StopSessionLog tabObj
    summaryStream.WriteLine "[" & Now & "] Tab finished: " & deviceName & ", log: " & logPath
    summaryStream.WriteLine String(72, "-")
End Sub

Sub SendPasswordDecisionNo(ByRef screenObj)
    ' 等待设备完整显示输入提示，再逐字符发送 NO 和回车，避免部分字符丢失。
    crt.Sleep 200
    screenObj.Send "N"
    crt.Sleep 100
    screenObj.Send "O"
    crt.Sleep 100
    screenObj.Send vbCr
End Sub

Function HasVisiblePasswordDecisionPrompt(ByRef screenObj)
    Dim screenText, startRow
    On Error Resume Next
    HasVisiblePasswordDecisionPrompt = False
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
    waitTexts = Array("[Y/N]:", ">", "]", "#", "$", "%")
    decisionCount = 0
    WaitForLoginPrompt = 0
    On Error Resume Next

    Do
        matchIndex = screenObj.WaitForStrings(waitTexts, timeoutSeconds)
        If Err.Number <> 0 Then
            Err.Clear
            On Error GoTo 0
            Exit Function
        End If
        If matchIndex = 0 Then Exit Function

        rowText = Trim(screenObj.Get(screenObj.CurrentRow, 1, screenObj.CurrentRow, screenObj.Columns))
        If matchIndex = 1 Or InStr(1, rowText, "[Y/N]", vbTextCompare) > 0 Then
            decisionCount = decisionCount + 1
            If decisionCount > 3 Then Exit Function
            SendPasswordDecisionNo screenObj
            If Err.Number <> 0 Then
                Err.Clear
                On Error GoTo 0
                Exit Function
            End If
        Else
            WaitForLoginPrompt = matchIndex
            Exit Do
        End If
    Loop
    On Error GoTo 0
End Function

Function ExtractDeviceNameFromPrompt(ByVal promptText)
    Dim re, matches
    Set re = New RegExp
    re.Global = False
    re.IgnoreCase = True
    re.Pattern = "[<\[]([A-Z0-9_.\s-]+)[>\]]"
    Set matches = re.Execute(promptText)
    If matches.Count > 0 Then
        ExtractDeviceNameFromPrompt = UCase(matches(0).SubMatches(0))
    Else
        ExtractDeviceNameFromPrompt = ""
    End If
End Function

Function ExtractDeviceNameFromText(ByVal sourceText)
    Dim re, matches
    Set re = New RegExp
    re.Global = False
    re.IgnoreCase = True
    re.Pattern = "([A-Z0-9_.\s-]{3,60})"
    Set matches = re.Execute(sourceText)
    If matches.Count > 0 Then
        ExtractDeviceNameFromText = UCase(matches(0).Value)
    Else
        ExtractDeviceNameFromText = ""
    End If
End Function

Function SanitizeFileName(ByVal name)
    Dim re
    Set re = New RegExp
    re.Global = True
    re.Pattern = "[^A-Za-z0-9_.-]"
    SanitizeFileName = re.Replace(name, "_")
End Function

Function GetCommandsForSession(ByVal sessionName)
    GetCommandsForSession = Array( _
        "display version", _
        "display device", _
        "display startup", _
        "dis cpu", _
        "dis cpu-usage", _
        "dis memory", _
        "dis memory-usage", _
        "dis memory all", _
        "display interface brief", _
        "display ip interface brief", _
        "display current-configuration", _
        "display ip routing-table", _
        "display logbuffer" _
    )
End Function

Function SendCommandAndWait(ByRef screenObj, ByVal prompt, ByVal commandText, ByVal timeoutSeconds, ByVal maxMoreCount)
    screenObj.Send commandText & vbCr
    SendCommandAndWait = WaitForPromptOrHandleMore(screenObj, prompt, timeoutSeconds, maxMoreCount)
End Function

Function WaitForPromptOrHandleMore(ByRef screenObj, ByVal prompt, ByVal timeoutSeconds, ByVal maxContinuousTimeout)
    Dim waitTexts, matchIndex, timeoutCount
    Dim baseWait

    ' Build wait list: More indicators, then optional prompt
    baseWait = Array("---- More ----", "--More--", "Press any key to continue")
    If prompt <> "" Then
        ' Append prompt as last item
        ReDim waitTexts(UBound(baseWait) + 1)
        Dim j
        For j = 0 To UBound(baseWait)
            waitTexts(j) = baseWait(j)
        Next
        waitTexts(UBound(waitTexts)) = prompt
    Else
        waitTexts = baseWait
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
            ' Instead of break, send space to try to wake up
            screenObj.Send " "
        ElseIf matchIndex >= 1 And matchIndex <= UBound(baseWait) + 1 Then
            ' Matched a More indicator
            timeoutCount = 0
            screenObj.Send " "
        Else
            ' Matched the prompt (last index)
            WaitForPromptOrHandleMore = True
            Exit Function
        End If
    Loop
End Function

Function StartSessionLog(ByRef tabObj, ByVal logPath)
    On Error Resume Next
    If tabObj.Session.Logging Then
        tabObj.Session.Log False
    End If
    tabObj.Session.LogFileName = logPath
    tabObj.Session.Log True
    If Err.Number <> 0 Then
        StartSessionLog = False
        Err.Clear
    Else
        StartSessionLog = True
    End If
    On Error GoTo 0
End Function

Sub StopSessionLog(ByRef tabObj)
    On Error Resume Next
    If tabObj.Session.Logging Then
        tabObj.Session.Log False
    End If
    On Error GoTo 0
End Sub

Function BuildLogRoot()
    Dim basePath, logRoot, systemName, dateFolder
    basePath = Left(crt.ScriptFullName, InStrRev(crt.ScriptFullName, "\") - 1)
    dateFolder = Year(Date) & "-" & Month(Date) & "-" & Day(Date)
    systemName = "NM1"
    BuildLogRoot = g_fso.BuildPath(basePath, "logs\" & dateFolder & "\" & systemName)
End Function

Function IsTabConnected(ByRef tabObj)
    On Error Resume Next
    IsTabConnected = False
    If Not tabObj Is Nothing Then
        If tabObj.Session.Connected Then
            IsTabConnected = True
        End If
    End If
    On Error GoTo 0
End Function

Function GetTabCaptionSafe(ByRef tabObj)
    On Error Resume Next
    GetTabCaptionSafe = ""
    If Not tabObj Is Nothing Then
        GetTabCaptionSafe = tabObj.Caption
    End If
    On Error GoTo 0
End Function

Sub EnsureFolderExists(ByVal folderPath)
    Dim parentPath
    If g_fso.FolderExists(folderPath) Then Exit Sub
    parentPath = g_fso.GetParentFolderName(folderPath)
    if Len(parentPath) > 0 And Not g_fso.FolderExists(parentPath) Then
        EnsureFolderExists parentPath
    End If
    g_fso.CreateFolder folderPath
End Sub

Function TimeStampForFile(ByVal dt)
    TimeStampForFile = Year(dt) & _
        Right("0" & Month(dt), 2) & _
        Right("0" & Day(dt), 2) & "_" & _
        Right("0" & Hour(dt), 2) & _
        Right("0" & Minute(dt), 2) & _
        Right("0" & Second(dt), 2)
End Function
