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
    summaryPath = g_fso.BuildPath(logRoot, "NM2_summary_" & runStamp & ".log")
    Set summaryStream = g_fso.OpenTextFile(summaryPath, ForWriting, True)
    summaryStream.WriteLine "NetMgmt-2 daily check started: " & Now
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
    summaryStream.WriteLine "NetMgmt-2 daily check finished: " & Now
    summaryStream.Close

    crt.Dialog.MessageBox "Daily check finished. Log directory:" & vbCrLf & logRoot, "SecureCRT Daily Check"
End Sub

Sub RunCheckForTab(ByRef tabObj, ByVal logRoot, ByRef summaryStream)
    Dim screenObj, logPath, commandList
    Dim connectOk, prompt, disablePagerCmd
    Dim index, commandText, deviceName, matchIdx

    If Not IsTabConnected(tabObj) Then
        summaryStream.WriteLine "[" & Now & "] Tab not connected, skip caption: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    Set screenObj = tabObj.Screen
    screenObj.Synchronous = True

    tabObj.Activate
    screenObj.Send vbCr
    
    ' �����ʾ�� (��Ϊ����Ϊ > �� ]����Ȩģʽ����Ϊ #)
    matchIdx = screenObj.WaitForStrings(Array(">", "]", "#"), 10)
    If matchIdx = 0 Then
        summaryStream.WriteLine "[" & Now & "] Prompt not detected after Enter, skip tab: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    ' ����ʵ�ʵ���ʾ��
    Dim curRow, curLine
    curRow = screenObj.CurrentRow
    curLine = Trim(screenObj.Get(curRow, 1, curRow, screenObj.Columns))
    prompt = curLine
    
    ' ��ȡ�������� IP ��Ϊ�ļ��� (����ʹ�ñ�ǩҳ����)
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

    logPath = g_fso.BuildPath(logRoot, "NM2_" & Replace(deviceName, " ", "_") & "_" & TimeStampForFile(Now) & ".log")
    StartSessionLog tabObj, logPath

    disablePagerCmd = "screen-length 0 temporary"
    SendCommandAndWait screenObj, prompt, disablePagerCmd, 10, 1

    commandList = GetCommandsForSession(deviceName)
    For index = 0 To UBound(commandList)
        commandText = commandList(index)
        If Len(Trim(commandText)) > 0 Then
            summaryStream.WriteLine "[" & Now & "] " & deviceName & " run command: " & commandText
            If Not SendCommandAndWait(screenObj, prompt, commandText, 120, 3) Then
                summaryStream.WriteLine "[" & Now & "] " & deviceName & " command may have timed out: " & commandText
            End If
        End If
    Next

    StopSessionLog tabObj
    summaryStream.WriteLine "[" & Now & "] Tab finished: " & deviceName & ", log: " & logPath
    summaryStream.WriteLine String(72, "-")
End Sub

Function ExtractDeviceNameFromPrompt(ByVal promptText)
    Dim re, matches
    Set re = New RegExp
    re.Global = False
    re.IgnoreCase = True
    ' ƥ�� <NAME> �� [NAME] ��ʽ
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
    ' Update pattern to support spaces, dots and longer names
    re.Pattern = "([A-Z0-9_.\s-]{3,60})"

    Set matches = re.Execute(sourceText)
    If matches.Count > 0 Then
        ExtractDeviceNameFromText = UCase(matches(0).Value)
    Else
        ExtractDeviceNameFromText = ""
    End If
    End Function

Function GetCommandsForSession(ByVal sessionName)
    ' ����Ѳ���׼���
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

    waitTexts = Array( _
        "---- More ----", _
        "--More--", _
        "Press any key to continue", _
        prompt _
    )

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
        ElseIf matchIndex >= 4 Then
            WaitForPromptOrHandleMore = True
            Exit Function
        End If
    Loop
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
    Dim basePath, logRoot, systemName, dateFolder
    basePath = Left(crt.ScriptFullName, InStrRev(crt.ScriptFullName, "\") - 1)
    dateFolder = Year(Date) & "-" & Month(Date) & "-" & Day(Date)
    systemName = "NM2"
    
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
