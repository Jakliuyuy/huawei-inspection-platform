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
    summaryPath = g_fso.BuildPath(logRoot, "Softswitch_summary_" & runStamp & ".log")
    Set summaryStream = g_fso.OpenTextFile(summaryPath, ForWriting, True)
    summaryStream.WriteLine "Softswitch daily check started: " & Now
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
            RunCheckForTab tabObj, logRoot, summaryStream
        End If
    Next

    summaryStream.WriteLine String(72, "=")
    summaryStream.WriteLine "Softswitch daily check finished: " & Now
    summaryStream.Close

    crt.Dialog.MessageBox "Daily check finished. Log directory:" & vbCrLf & logRoot, "SecureCRT Daily Check"
End Sub

Sub RunCheckForTab(ByRef tabObj, ByVal logRoot, ByRef summaryStream)
    Dim screenObj, logPath, commandList
    Dim prompt, deviceName, matchIdx, commandText
    Dim index, commandTimeout, maxRetries

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

    matchIdx = WaitForLoginPrompt(screenObj, 10)
    If matchIdx = 0 Then
        summaryStream.WriteLine "[" & Now & "] Prompt not detected after Enter, skip tab: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    Dim curRow, curLine
    curRow = screenObj.CurrentRow
    curLine = Trim(screenObj.Get(curRow, 1, curRow, screenObj.Columns))
    prompt = curLine

    deviceName = ExtractDeviceNameFromText(GetTabCaptionSafe(tabObj))
    If Len(deviceName) = 0 Then
        deviceName = ExtractDeviceNameFromPrompt(prompt)
    End If
    If Len(deviceName) = 0 Then
        summaryStream.WriteLine "[" & Now & "] Device name not detected, skip tab: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    If g_seenDevices.Exists(deviceName) Then
        summaryStream.WriteLine "[" & Now & "] Device already processed, skip duplicate tab: " & deviceName
        Exit Sub
    End If
    g_seenDevices.Add deviceName, True

    summaryStream.WriteLine "[" & Now & "] Start tab: " & deviceName & " detected prompt: " & prompt

    logPath = g_fso.BuildPath(logRoot, "Softswitch_" & Replace(deviceName, " ", "_") & "_" & TimeStampForFile(Now) & ".log")
    StartSessionLog tabObj, logPath

    If Not DisablePaging(screenObj, prompt, summaryStream, deviceName) Then
        summaryStream.WriteLine "[" & Now & "] " & deviceName & " WARNING: Failed to disable paging, may cause incomplete output."
    End If

    commandList = GetCommandsForSession(deviceName)
    maxRetries = 2
    For index = 0 To UBound(commandList)
        commandText = commandList(index)
        If Len(Trim(commandText)) > 0 Then
            commandTimeout = GetCommandTimeout(commandText)
            summaryStream.WriteLine "[" & Now & "] " & deviceName & " run command: " & commandText
            If Not SendCommandAndWaitEx(screenObj, prompt, commandText, commandTimeout, maxRetries, summaryStream, deviceName) Then
                summaryStream.WriteLine "[" & Now & "] " & deviceName & " command TIMEOUT: " & commandText
            End If
        End If
    Next

    StopSessionLog tabObj
    summaryStream.WriteLine "[" & Now & "] Tab finished: " & deviceName & ", log: " & logPath
    summaryStream.WriteLine String(72, "-")
End Sub

Function GetCommandTimeout(ByVal commandText)
    commandText = LCase(commandText)
    If InStr(commandText, "display current-configuration") > 0 Or _
       InStr(commandText, "display startup") > 0 Or _
       InStr(commandText, "display logbuffer") > 0 Then
        GetCommandTimeout = 60
    Else
        GetCommandTimeout = 20
    End If
End Function

Function DisablePaging(ByRef screenObj, ByVal prompt, ByRef summaryStream, ByVal deviceName)
    Dim pagingCommands, cmd
    pagingCommands = Array( _
        "screen-length 0", _
        "undo screen-length", _
        "screen-length disable" _
    )
    DisablePaging = False
    For Each cmd In pagingCommands
        screenObj.Send cmd & vbCr
        If screenObj.WaitForString(cmd, 5) Then
            If WaitForPromptOrHandleMoreEx(screenObj, prompt, 15, 3, summaryStream, deviceName) Then
                Dim lastLine
                lastLine = Trim(screenObj.Get(screenObj.CurrentRow, 1, screenObj.CurrentRow, screenObj.Columns))
                If InStr(1, lastLine, "Error", vbTextCompare) = 0 And _
                   InStr(1, lastLine, "Unrecognized", vbTextCompare) = 0 Then
                    DisablePaging = True
                    Exit Function
                End If
            End If
        End If
    Next
End Function

Function SendCommandAndWaitEx(ByRef screenObj, ByVal prompt, ByVal commandText, ByVal timeoutSeconds, ByVal maxMoreRetries, ByRef summaryStream, ByVal deviceName)
    screenObj.Send commandText & vbCr
    If Not screenObj.WaitForString(commandText, 5) Then
        SendCommandAndWaitEx = False
        Exit Function
    End If
    SendCommandAndWaitEx = WaitForPromptOrHandleMoreEx(screenObj, prompt, timeoutSeconds, maxMoreRetries, summaryStream, deviceName)
End Function

Function WaitForPromptOrHandleMoreEx(ByRef screenObj, ByVal prompt, ByVal timeoutSeconds, ByVal maxContinuousTimeout, ByRef summaryStream, ByVal deviceName)
    Dim waitTexts, matchIndex, timeoutCount, moreCount, lastRow
    waitTexts = Array("---- More ----", "--More--", "Press any key to continue", prompt)
    timeoutCount = 0
    moreCount = 0

    Do
        matchIndex = screenObj.WaitForStrings(waitTexts, timeoutSeconds)
        If matchIndex = 0 Then
            timeoutCount = timeoutCount + 1
            If timeoutCount >= maxContinuousTimeout Then
                summaryStream.WriteLine "[" & Now & "] " & deviceName & " waiting for prompt timed out, sending Ctrl+C"
                screenObj.Send vbCancel
                crt.Sleep 1000
                WaitForPromptOrHandleMoreEx = False
                Exit Function
            End If
        ElseIf matchIndex >= 1 And matchIndex <= 3 Then
            timeoutCount = 0
            moreCount = moreCount + 1
            screenObj.Send " "
            crt.Sleep 100
        ElseIf matchIndex >= 4 Then
            crt.Sleep 1000
            lastRow = screenObj.CurrentRow
            Dim i, errLine
            For i = 1 To 5
                If lastRow - i > 0 Then
                    errLine = Trim(screenObj.Get(lastRow - i, 1, lastRow - i, screenObj.Columns))
                    If InStr(1, errLine, "Error", vbTextCompare) > 0 Or _
                       InStr(1, errLine, "Unrecognized", vbTextCompare) > 0 Then
                        summaryStream.WriteLine "[" & Now & "] " & deviceName & " command may have error: " & errLine
                        Exit For
                    End If
                End If
            Next
            WaitForPromptOrHandleMoreEx = True
            Exit Function
        End If
    Loop
End Function

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

Function GetCommandsForSession(ByVal sessionName)
    GetCommandsForSession = Array( _
        "display version", _
        "display device", _
        "display startup", _
        "dis cpu-usage", _
        "dis memory", _
        "display interface", _
        "display interface brief", _
        "display ip interface brief", _
        "display ip routing-table", _
        "dis alarm urgent", _
        "display logbuffer", _
        "display current-configuration" _
    )
End Function

Sub StartSessionLog(ByRef tabObj, ByVal logPath)
    On Error Resume Next
    If tabObj.Session.Logging Then
        tabObj.Session.Log False
    End If
    tabObj.Session.LogFileName = logPath
    tabObj.Session.Log True
    On Error GoTo 0
End Sub

Sub StopSessionLog(ByRef tabObj)
    On Error Resume Next
    If tabObj.Session.Logging Then
        tabObj.Session.Log False
    End If
    On Error GoTo 0
End Sub

Function BuildLogRoot()
    Dim basePath, systemName, dateFolder
    basePath = Left(crt.ScriptFullName, InStrRev(crt.ScriptFullName, "\") - 1)
    dateFolder = Year(Date) & "-" & Month(Date) & "-" & Day(Date)
    systemName = "Softswitch"
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
    If Len(parentPath) > 0 And Not g_fso.FolderExists(parentPath) Then
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
