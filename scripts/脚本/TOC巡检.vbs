' $language = "VBScript"
' $interface = "1.0"

Option Explicit

Const ForReading = 1
Const ForWriting = 2

Dim g_fso, g_seenIps
Set g_fso = CreateObject("Scripting.FileSystemObject")
Set g_seenIps = CreateObject("Scripting.Dictionary")

Sub Main()
    Dim logRoot, summaryPath, summaryStream
    Dim tabCount, i, tabObj, runStamp

    ' 1. Setup Logging
    logRoot = BuildLogRoot()
    EnsureFolderExists logRoot

    runStamp = TimeStampForFile(Now)
    summaryPath = g_fso.BuildPath(logRoot, "TOC_summary_" & runStamp & ".log")
    Set summaryStream = g_fso.OpenTextFile(summaryPath, ForWriting, True)
    summaryStream.WriteLine "TOC Check started: " & Now
    summaryStream.WriteLine "Log directory: " & logRoot
    summaryStream.WriteLine String(72, "=")

    ' 2. Iterate Tabs
    tabCount = crt.GetTabCount()
    If tabCount <= 0 Then
        summaryStream.WriteLine "No open tab found."
        summaryStream.Close
        crt.Dialog.MessageBox "No open tab found.", "TOC Check"
        Exit Sub
    End If

    g_seenIps.RemoveAll
    For i = 1 To tabCount
        Set tabObj = crt.GetTab(i)
        if Not tabObj Is Nothing Then
            ProcessTab tabObj, logRoot, summaryStream
        End If
    Next

    summaryStream.WriteLine String(72, "=")
    summaryStream.WriteLine "TOC Check finished: " & Now
    summaryStream.Close

    crt.Dialog.MessageBox "TOC Check finished. Logs in: " & vbCrLf & logRoot, "TOC Check"
End Sub

Sub ProcessTab(ByRef tabObj, ByVal logRoot, ByRef summaryStream)
    Dim ip, label, commands, pagerCommand, promptHint
    Dim screenObj, promptText, logPath, i, cmdArr, found, deviceName

    If Not tabObj.Session.Connected Then
        summaryStream.WriteLine "[" & Now & "] Skip (not connected): " & tabObj.Caption
        Exit Sub
    End If

    tabObj.Activate
    Set screenObj = tabObj.Screen
    screenObj.Synchronous = True
    screenObj.Send vbCr

    If Not WaitForPrompt(screenObj, "", 10, 2) Then
        summaryStream.WriteLine "[" & Now & "] Error (prompt timeout): " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    promptText = DetectPromptText(screenObj)
    
    ' ��ȡ��������Ϊ�ļ��� (����ʹ�ñ�ǩҳ����)
    deviceName = ExtractDeviceNameFromText(GetTabCaptionSafe(tabObj))
    If Len(deviceName) = 0 Then
        deviceName = ExtractDeviceNameFromPrompt(promptText)
    End If

    If Len(deviceName) = 0 Then
        summaryStream.WriteLine "[" & Now & "] Device name not detected, skip tab: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    ' --- Embedded TOC Configuration Matching ---
    found = GetTOCConfig(tabObj, ip, label, promptHint, pagerCommand, commands)
    If Not found Then
        ' Fallback if not specifically matched in GetTOCConfig
        ip = deviceName
        label = deviceName
    End If

    If g_seenIps.Exists(deviceName) Then
        summaryStream.WriteLine "[" & Now & "] Skip (duplicate device): " & deviceName
        Exit Sub
    End If
    g_seenIps.Add deviceName, True

    logPath = g_fso.BuildPath(logRoot, "TOC_" & Replace(deviceName, " ", "_") & "_" & TimeStampForFile(Now) & ".log")
    
    StartSessionLog tabObj, logPath
    summaryStream.WriteLine "[" & Now & "] Run: " & deviceName

    ' Disable Pager
    SendCommand screenObj, promptText, pagerCommand, 10

    ' Run TOC Commands
    cmdArr = Split(commands, ";;")
    For i = 0 To UBound(cmdArr)
        If Len(Trim(cmdArr(i))) > 0 Then
            SendCommand screenObj, promptText, cmdArr(i), 120 ' Longer timeout for license/alarm cmds
        End If
    Next

    StopSessionLog tabObj
    summaryStream.WriteLine "[" & Now & "] Finished: " & deviceName
End Sub

Function GetTOCConfig(ByRef tabObj, ByRef ip, ByRef label, ByRef promptHint, ByRef pager, ByRef commands)
    Dim caption, host, matched
    caption = tabObj.Caption
    On Error Resume Next
    host = tabObj.Session.Config.GetOption("Hostname")
    On Error GoTo 0
    matched = False

    ' TOC Specific Device Matching (Modify targetIp with real ones if known)
    ' Defaulting to 0.0.0.0 if unknown, matching by JZ-TOC label
    
    ' Format: MatchEntry(searchValue, matchIp, matchHint, outIp, outLabel, outHint, outPager, outCmds)
    If Not matched Then matched = MatchTOCEntry(host, caption, "10.237.113.193", "JZ-TOC-EOR01BHW", ip, label, promptHint, pager, commands)
    If Not matched Then matched = MatchTOCEntry(host, caption, "10.237.113.192", "JZ-TOC-EOR02BHW", ip, label, promptHint, pager, commands)
    If Not matched Then matched = MatchTOCEntry(host, caption, "10.237.113.236", "JZ-TOC-EOR06BHW", ip, label, promptHint, pager, commands)
    If Not matched Then matched = MatchTOCEntry(host, caption, "10.237.113.209", "JZ-TOC-SACE01BHW", ip, label, promptHint, pager, commands)
    If Not matched Then matched = MatchTOCEntry(host, caption, "10.237.113.213", "JZ-TOC-SACE02BHW", ip, label, promptHint, pager, commands)
    
    ' Generic matching for other JZ-TOC devices
    If Not matched And InStr(UCase(caption), "JZ-TOC") > 0 Then
        ip = host : If Len(ip) = 0 Then ip = "UnknownIP"
        label = caption
        promptHint = "JZ-TOC"
        pager = "screen-length 0 temporary"
        commands = "display version;;display device;;dis alarm active;;dis cpu;;dis cpu-usage;;dis memory;;dis memory-usage;;dis memory all;;display interface brief;;display ip interface brief;;display current-configuration;;display ip routing-table;;display logbuffer"
        matched = True
    End If

    ' FINAL FALLBACK: If it's a connected session, don't skip it, just use generic commands
    If Not matched Then
        ip = host : If Len(ip) = 0 Then ip = "UnknownIP"
        label = caption
        promptHint = ""
        pager = "screen-length 0 temporary"
        commands = "display version;;display device;;dis alarm active;;dis cpu;;dis cpu-usage;;dis memory;;dis memory-usage;;dis memory all;;display interface brief;;display ip interface brief;;display current-configuration;;display ip routing-table;;display logbuffer"
        matched = True
    End If

    GetTOCConfig = matched
End Function

Function MatchTOCEntry(host, caption, targetIp, targetHint, outIp, outLabel, outHint, outPager, outCmds)
    If host = targetIp Or InStr(caption, targetIp) > 0 Or InStr(caption, targetHint) > 0 Then
        outIp = targetIp
        outLabel = targetHint
        outHint = targetHint
        outPager = "screen-length 0 temporary"
        ' TOC Standard commands
        outCmds = "display version;;display device;;dis alarm active;;dis cpu;;dis cpu-usage;;dis memory;;dis memory-usage;;dis memory all;;display interface brief;;display ip interface brief;;display current-configuration;;display ip routing-table;;display logbuffer"
        
        ' Specific commands for license-bearing devices
        If InStr(targetHint, "SACE") > 0 Then
            outCmds = outCmds & ";;display license;;display license esn"
        End If
        MatchTOCEntry = True
    Else
        MatchTOCEntry = False
    End If
End Function

Function SendCommand(ByRef screenObj, ByVal prompt, ByVal cmd, ByVal timeout)
    screenObj.Send cmd & vbCr
    SendCommand = WaitForPrompt(screenObj, prompt, timeout, 2)
End Function

Function WaitForPrompt(ByRef screenObj, ByVal prompt, ByVal timeout, ByVal retries)
    Dim targets, res, count
    If Len(prompt) > 0 Then
        targets = Array("---- More ----", "--More--", "Press any key", "[Y/N]:", prompt)
    Else
        ' Removed ":" from here to avoid matching "Info:" or time strings
        targets = Array("---- More ----", "--More--", "Press any key", "[Y/N]:", ">", "#", "]")
    End If

    count = 0
    Do
        res = screenObj.WaitForStrings(targets, timeout)
        If res = 0 Then
            count = count + 1
            If count >= retries Then WaitForPrompt = False : Exit Function
            screenObj.Send vbCr
        ElseIf res >= 1 And res <= 3 Then
            screenObj.Send " "
        ElseIf res = 4 Then
            ' Handle [Y/N]: by sending 'n' and continuing to wait
            screenObj.Send "n"
            crt.Sleep 100
            screenObj.Send vbCr
            count = 0 
        Else
            ' Found a real prompt (> or # or ])
            WaitForPrompt = True : Exit Function
        End If
    Loop
End Function

Function DetectPromptText(ByRef screenObj)
    Dim text, row, i
    ' Search current and previous rows for a valid prompt ending
    For i = 0 To 1
        row = screenObj.CurrentRow - i
        If row >= 1 Then
            text = Trim(screenObj.Get(row, 1, row, screenObj.Columns))
            ' Valid prompt usually ends with >, #, or ]
            If Right(text, 1) = ">" Or Right(text, 1) = "#" Or Right(text, 1) = "]" Then
                DetectPromptText = text
                Exit Function
            End If
        End If
    Next
    DetectPromptText = ""
End Function

Function BuildLogRoot()
    Dim basePath, logRoot, systemName, dateFolder
    basePath = Left(crt.ScriptFullName, InStrRev(crt.ScriptFullName, "\") - 1)
    dateFolder = Year(Date) & "-" & Month(Date) & "-" & Day(Date)
    systemName = "TOC"
    
    BuildLogRoot = g_fso.BuildPath(basePath, "logs\" & dateFolder & "\" & systemName)
End Function

Sub EnsureFolderExists(ByVal path)
    Dim p
    If g_fso.FolderExists(path) Then Exit Sub
    p = g_fso.GetParentFolderName(path)
    If Len(p) > 0 Then EnsureFolderExists p
    g_fso.CreateFolder path
End Sub

Sub StartSessionLog(ByRef tabObj, ByVal path)
    On Error Resume Next
    tabObj.Session.Log False
    tabObj.Session.LogFileName = path
    tabObj.Session.Log True
    On Error GoTo 0
End Sub

Sub StopSessionLog(ByRef tabObj)
    On Error Resume Next
    tabObj.Session.Log False
    On Error GoTo 0
End Sub

Function TimeStampForFile(ByVal dt)
    TimeStampForFile = Year(dt) & Right("0" & Month(dt), 2) & Right("0" & Day(dt), 2) & "_" & Right("0" & Hour(dt), 2) & Right("0" & Minute(dt), 2)
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
    ' 匹配 TOC 设备名称格式，支持空格、点号等，长度3-60
    re.Pattern = "([A-Z0-9_.\s-]{3,60})"

    Set matches = re.Execute(sourceText)
    If matches.Count > 0 Then
        ExtractDeviceNameFromText = UCase(Trim(matches(0).Value))
    Else
        ExtractDeviceNameFromText = ""
    End If
End Function

Function GetTabCaptionSafe(ByRef tabObj)
    On Error Resume Next
    GetTabCaptionSafe = ""
    If Not tabObj Is Nothing Then
        GetTabCaptionSafe = tabObj.Caption
    End If
    On Error GoTo 0
End Function

Function SanitizeFileName(ByVal txt)
    Dim arr, i
    arr = Array("\", "/", ":", "*", "?", """", "<", ">", "|", " ")
    For i = 0 To UBound(arr) : txt = Replace(txt, arr(i), "_") : Next
    SanitizeFileName = txt
End Function
