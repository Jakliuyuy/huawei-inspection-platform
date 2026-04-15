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
    summaryPath = g_fso.BuildPath(logRoot, "TOB_summary_" & runStamp & ".log")
    Set summaryStream = g_fso.OpenTextFile(summaryPath, ForWriting, True)
    summaryStream.WriteLine "TOB daily check started: " & Now
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
    summaryStream.WriteLine "TOB daily check finished: " & Now
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
    
    ' ���Լ���κ���ʽ����ʾ�� (��Ϊ����Ϊ > �� ]����Ȩģʽ����Ϊ #)
    matchIdx = screenObj.WaitForStrings(Array(">", "]", "#"), 10)
    If matchIdx = 0 Then
        summaryStream.WriteLine "[" & Now & "] Prompt not detected after Enter, skip tab: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    ' �ӵ�ǰ�в���ʵ�ʵ���ʾ��
    Dim curRow, curLine
    curRow = screenObj.CurrentRow
    curLine = Trim(screenObj.Get(curRow, 1, curRow, screenObj.Columns))
    prompt = curLine
    
    ' �����ʾ��̫�������������������������ȡ���һ����
    If Len(prompt) > 60 Then prompt = Right(prompt, 30)

    ' ��ȡ��������Ϊ�ļ��� (����ʹ�ñ�ǩҳ����)
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

    logPath = g_fso.BuildPath(logRoot, "TOB_" & Replace(deviceName, " ", "_") & "_" & TimeStampForFile(Now) & ".log")
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
    ' 匹配 <NAME> 或 [NAME] 格式，支持空格和点号
    re.Pattern = "[<\[]([A-Z0-9_.\s-]+)[>\]]"

    Set matches = re.Execute(promptText)
    If matches.Count > 0 Then
        ExtractDeviceNameFromPrompt = UCase(Trim(matches(0).SubMatches(0)))
    Else
        ExtractDeviceNameFromPrompt = ""
    End If
End Function

Function GetCommandsForSession(ByVal sessionName)
    ' TOB Ѳ�쳣������
    GetCommandsForSession = Array( _
        "display version", _
        "display startup", _
        "display device", _
        "dis alarm active", _
        "display alarm urgent", _
        "dis cpu", _
        "dis cpu-usage", _
        "dis memory", _
        "dis memory-usage", _
        "dis memory all", _
        "display interface brief", _
        "display logbuffer", _
        "display current-configuration" _
    )
End Function

Function SendCommandAndWait(ByRef screenObj, ByVal prompt, ByVal commandText, ByVal timeoutSeconds, ByVal maxMoreCount)
    screenObj.Send commandText & vbCr
    SendCommandAndWait = WaitForPromptOrHandleMore(screenObj, prompt, timeoutSeconds, maxMoreCount)
End Function

Function WaitForPromptOrHandleMore(ByRef screenObj, ByVal prompt, ByVal timeoutSeconds, ByVal maxContinuousTimeout)
    Dim waitTexts, matchIndex, timeoutCount

    If Len(prompt) > 0 Then
        waitTexts = Array( _
            "---- More ----", _
            "---- More ( Press 'Q' to break ) ----", _
            "--More--", _
            prompt _
        )
    Else
        waitTexts = Array( _
            "---- More ----", _
            "---- More ( Press 'Q' to break ) ----", _
            "--More--", _
            ">", _
            "#" _
        )
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
    systemName = "TOB"
    
    BuildLogRoot = g_fso.BuildPath(basePath, "logs\" & dateFolder & "\" & systemName)
End Function

Function DetectDeviceName(ByRef tabObj, ByRef screenObj)
    Dim row, col, lineText, matches

    DetectDeviceName = ExtractDeviceNameFromText(GetTabCaptionSafe(tabObj))
    If Len(DetectDeviceName) > 0 Then
        Exit Function
    End If

    row = screenObj.CurrentRow
    If row < 1 Then
        row = 1
    End If

    lineText = screenObj.Get(row, 1, row, screenObj.Columns)
    DetectDeviceName = ExtractDeviceNameFromText(lineText)
    If Len(DetectDeviceName) > 0 Then
        Exit Function
    End If

    If row > 1 Then
        lineText = screenObj.Get(row - 1, 1, row - 1, screenObj.Columns)
        DetectDeviceName = ExtractDeviceNameFromText(lineText)
        If Len(DetectDeviceName) > 0 Then
            Exit Function
        End If
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
        ' 排除掉一些可能的非设备名关键字
        Dim val
        val = UCase(Trim(matches(0).Value))
        If val = "HUAWEI" Or val = "RETURN" Or val = "QUIT" Then
            ExtractDeviceNameFromText = ""
        Else
            ExtractDeviceNameFromText = val
        End If
    Else
        ExtractDeviceNameFromText = ""
    End If
End Function

Function IsTabConnected(ByRef tabObj)
    On Error Resume Next
    IsTabConnected = False

    If tabObj Is Nothing Then
        Exit Function
    End If

    If Err.Number <> 0 Then
        Err.Clear
    End If

    If tabObj.Session.Connected Then
        IsTabConnected = True
    End If

    If Err.Number <> 0 Then
        Err.Clear
        IsTabConnected = False
    End If
    On Error GoTo 0
End Function

Function GetTabCaptionSafe(ByRef tabObj)
    On Error Resume Next
    GetTabCaptionSafe = ""
    If Not tabObj Is Nothing Then
        GetTabCaptionSafe = tabObj.Caption
    End If
    If Err.Number <> 0 Then
        Err.Clear
        GetTabCaptionSafe = ""
    End If
    On Error GoTo 0
End Function

Sub EnsureFolderExists(ByVal folderPath)
    Dim parentPath

    If g_fso.FolderExists(folderPath) Then
        Exit Sub
    End If

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
