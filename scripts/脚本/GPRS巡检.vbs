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
    summaryPath = g_fso.BuildPath(logRoot, "GPRS_summary_" & runStamp & ".log")
    Set summaryStream = g_fso.OpenTextFile(summaryPath, ForWriting, True)
    summaryStream.WriteLine "GPRS daily check started: " & Now
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
    summaryStream.WriteLine "GPRS daily check finished: " & Now
    summaryStream.Close

    crt.Dialog.MessageBox "Daily check finished. Log directory:" & vbCrLf & logRoot, "SecureCRT Daily Check"
End Sub

Sub RunCheckForTab(ByRef tabObj, ByVal logRoot, ByRef summaryStream)
    Dim screenObj, logPath, finalLogPath, commandList
    Dim connectOk, prompt, disablePagerCmd
    Dim index, commandText, deviceName, matchIdx
    Dim captionText, deviceIp, fileStamp

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
    
    ' �����ʾ��
    matchIdx = WaitForLoginPrompt(screenObj, 10)
    If matchIdx = 0 Then
        summaryStream.WriteLine "[" & Now & "] Prompt not detected, skip tab: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    ' ����ʵ����ʾ��
    Dim curRow, curLine
    curRow = screenObj.CurrentRow
    curLine = Trim(screenObj.Get(curRow, 1, curRow, screenObj.Columns))
    prompt = curLine
    If Len(prompt) > 60 Then prompt = Right(prompt, 30)

    ' ��ȡ��������Ϊ�ļ��� (����ʹ�ñ�ǩҳ����)
    captionText = GetTabCaptionSafe(tabObj)
    deviceName = ExtractDeviceNameFromText(captionText)
    If Len(deviceName) = 0 Then
        deviceName = ExtractDeviceNameFromPrompt(prompt)
    End If
    deviceIp = ExtractIpFromText(captionText)
    If Len(deviceIp) = 0 Then
        deviceIp = ExtractIpFromText(prompt)
    End If
    
    If Len(deviceName) = 0 Then
        summaryStream.WriteLine "[" & Now & "] Device name not detected, skip tab: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    If g_seenDevices.Exists(deviceName) Then
        summaryStream.WriteLine "[" & Now & "] Device already processed, skip duplicate: " & deviceName
        Exit Sub
    End If
    g_seenDevices.Add deviceName, True

    summaryStream.WriteLine "[" & Now & "] Start tab: " & deviceName & " prompt: " & prompt

    fileStamp = TimeStampForFile(Now)
    logPath = BuildSessionLogPath(logRoot, deviceName, deviceIp, fileStamp)
    StartSessionLog tabObj, logPath

    disablePagerCmd = "screen-length 0 temporary"
    SendCommandAndWait screenObj, prompt, disablePagerCmd, 10, 1

    commandList = GetCommandsForSession(deviceName)
    For index = 0 To UBound(commandList)
        commandText = commandList(index)
        If Len(Trim(commandText)) > 0 Then
            summaryStream.WriteLine "[" & Now & "] " & deviceName & " run command: " & commandText
            If Not SendCommandAndWait(screenObj, prompt, commandText, 120, 3) Then
                summaryStream.WriteLine "[" & Now & "] " & deviceName & " command timed out: " & commandText
            End If
        End If
    Next

    StopSessionLog tabObj

    If Len(deviceIp) = 0 Then
        deviceIp = ExtractIpFromLogFile(logPath)
    End If

    finalLogPath = BuildSessionLogPath(logRoot, deviceName, deviceIp, fileStamp)
    If UCase(finalLogPath) <> UCase(logPath) Then
        If g_fso.FileExists(finalLogPath) Then
            summaryStream.WriteLine "[" & Now & "] Target log already exists, keep original: " & g_fso.GetFileName(logPath)
        Else
            On Error Resume Next
            g_fso.MoveFile logPath, finalLogPath
            If Err.Number = 0 Then
                logPath = finalLogPath
            Else
                summaryStream.WriteLine "[" & Now & "] Rename log failed: " & Err.Description
                Err.Clear
            End If
            On Error GoTo 0
        End If
    End If

    summaryStream.WriteLine "[" & Now & "] Tab finished: " & deviceName & " log: " & g_fso.GetFileName(logPath)
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
    ' 匹配 <NAME> 或 [NAME] 格式，支持空格和点号
    re.Pattern = "[<\[]([A-Z0-9_.\s-]+)[>\]]"
    Set matches = re.Execute(promptText)
    If matches.Count > 0 Then
        ExtractDeviceNameFromPrompt = UCase(Trim(matches(0).SubMatches(0)))
    Else
        ExtractDeviceNameFromPrompt = ""
    End If
End Function

Function ExtractDeviceNameFromText(ByVal sourceText)
    Dim re, matches
    Set re = New RegExp
    re.Global = False
    re.IgnoreCase = True
    ' 匹配设备名称格式，支持空格、点号等，长度3-60
    re.Pattern = "([A-Z0-9_.\s-]{3,60})"
    Set matches = re.Execute(sourceText)
    If matches.Count > 0 Then
        ExtractDeviceNameFromText = UCase(Trim(matches(0).Value))
    Else
        ExtractDeviceNameFromText = ""
    End If
End Function

Function ExtractIpFromText(ByVal sourceText)
    Dim re, matches, candidateIp
    Set re = New RegExp
    re.Global = False
    re.IgnoreCase = True
    re.Pattern = "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    Set matches = re.Execute(sourceText)
    If matches.Count > 0 Then
        candidateIp = Trim(matches(0).SubMatches(0))
        If IsUsableIp(candidateIp) Then
            ExtractIpFromText = candidateIp
            Exit Function
        End If
    End If
    ExtractIpFromText = ""
End Function

Function IsUsableIp(ByVal candidateIp)
    IsUsableIp = False
    If Len(candidateIp) = 0 Then Exit Function
    If Left(candidateIp, 4) = "127." Then Exit Function
    If Left(candidateIp, 2) = "0." Then Exit Function
    IsUsableIp = True
End Function

Function ExtractIpFromLogFile(ByVal logPath)
    Dim logStream, textContent
    On Error Resume Next
    If Not g_fso.FileExists(logPath) Then
        ExtractIpFromLogFile = ""
        Exit Function
    End If

    Set logStream = g_fso.OpenTextFile(logPath, ForReading, False)
    textContent = logStream.ReadAll
    logStream.Close
    If Err.Number <> 0 Then
        Err.Clear
        ExtractIpFromLogFile = ""
        Exit Function
    End If
    On Error GoTo 0

    ExtractIpFromLogFile = ExtractIpFromText(textContent)
End Function

Function BuildSessionLogPath(ByVal logRoot, ByVal deviceName, ByVal deviceIp, ByVal fileStamp)
    Dim safeName
    safeName = Replace(deviceName, " ", "_")
    If Len(Trim(deviceIp)) > 0 Then
        BuildSessionLogPath = g_fso.BuildPath(logRoot, "GPRS_" & safeName & "_" & deviceIp & "_" & fileStamp & ".log")
    Else
        BuildSessionLogPath = g_fso.BuildPath(logRoot, "GPRS_" & safeName & "_" & fileStamp & ".log")
    End If
End Function

Function GetCommandsForSession(ByVal sessionName)
    Dim nameUpper
    nameUpper = UCase(sessionName)
    
    If InStr(nameUpper, "LSNE20E") > 0 Then
        GetCommandsForSession = Array( _
            "dis system-alarm", _
            "display device", _
            "display cpu-usage", _
            "display memory-usage", _
            "dis ip interface brief", _
            "dis alarm active" _
        )
    Else
        GetCommandsForSession = Array( _
            "display device", _
            "display cpu-usage", _
            "display memory", _
            "display ip interface brief", _
            "dis alarm active", _
            "dis interface brief" _
        )
    End If
End Function

Function SendCommandAndWait(ByRef screenObj, ByVal prompt, ByVal commandText, ByVal timeoutSeconds, ByVal maxMoreCount)
    screenObj.Send commandText & vbCr
    SendCommandAndWait = WaitForPromptOrHandleMore(screenObj, prompt, timeoutSeconds, maxMoreCount)
End Function

Function WaitForPromptOrHandleMore(ByRef screenObj, ByVal prompt, ByVal timeoutSeconds, ByVal maxContinuousTimeout)
    Dim waitTexts, matchIndex, timeoutCount
    waitTexts = Array("---- More ----", "--More--", "Press any key", prompt)

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
        ElseIf matchIndex = 4 Then
            WaitForPromptOrHandleMore = True
            Exit Function
        End If
    Loop
End Function

Sub StartSessionLog(ByRef tabObj, ByVal logPath)
    On Error Resume Next
    If tabObj.Session.Logging Then tabObj.Session.Log False
    tabObj.Session.LogFileName = logPath
    tabObj.Session.Log True
    On Error GoTo 0
End Sub

Sub StopSessionLog(ByRef tabObj)
    On Error Resume Next
    If tabObj.Session.Logging Then tabObj.Session.Log False
    On Error GoTo 0
End Sub

Function BuildLogRoot()
    Dim basePath, logRoot, systemName, dateFolder
    basePath = Left(crt.ScriptFullName, InStrRev(crt.ScriptFullName, "\") - 1)
    dateFolder = Year(Date) & "-" & Month(Date) & "-" & Day(Date)
    systemName = "GPRS"
    
    BuildLogRoot = g_fso.BuildPath(basePath, "logs\" & dateFolder & "\" & systemName)
End Function

Function IsTabConnected(ByRef tabObj)
    On Error Resume Next
    IsTabConnected = False
    If Not tabObj Is Nothing Then
        If tabObj.Session.Connected Then IsTabConnected = True
    End If
    On Error GoTo 0
End Function

Function GetTabCaptionSafe(ByRef tabObj)
    On Error Resume Next
    GetTabCaptionSafe = ""
    If Not tabObj Is Nothing Then GetTabCaptionSafe = tabObj.Caption
    On Error GoTo 0
End Function

Sub EnsureFolderExists(ByVal folderPath)
    Dim parentPath
    If g_fso.FolderExists(folderPath) Then Exit Sub
    parentPath = g_fso.GetParentFolderName(folderPath)
    If Len(parentPath) > 0 And Not g_fso.FolderExists(parentPath) Then EnsureFolderExists parentPath
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
