' $language = "VBScript"
' $interface = "1.0"

Option Explicit

Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

Dim g_fso, g_seenDevices
Set g_fso = CreateObject("Scripting.FileSystemObject")
Set g_seenDevices = CreateObject("Scripting.Dictionary")
Dim g_tabCount

Sub Main()
    Dim tabCount, logRoot, summaryPath, summaryStream
    Dim i, tabObj, runStamp, systemName

    ' 系统标识
    systemName = "IDC"
    logRoot = BuildLogRoot(systemName)
    EnsureFolderExists logRoot

    runStamp = TimeStampForFile(Now)
    summaryPath = g_fso.BuildPath(logRoot, systemName & "_summary_" & runStamp & ".log")
    Set summaryStream = g_fso.OpenTextFile(summaryPath, ForWriting, True)
    summaryStream.WriteLine systemName & " daily check started: " & Now
    summaryStream.WriteLine "Log directory: " & logRoot
    summaryStream.WriteLine String(72, "=")

    crt.Screen.Synchronous = True
    g_seenDevices.RemoveAll
    g_tabCount = crt.GetTabCount()

    If g_tabCount <= 0 Then
        summaryStream.WriteLine "No open tab found."
        summaryStream.Close
        crt.Dialog.MessageBox "No open tab found.", "SecureCRT IDC Check"
        Exit Sub
    End If

    ' 初始唤醒
    GlobalPulse 1

    For i = 1 To g_tabCount
        Set tabObj = crt.GetTab(i)
        If Not tabObj Is Nothing Then
            RunCheckForTab tabObj, logRoot, summaryStream, systemName, i
        End If
    Next

    summaryStream.WriteLine String(72, "=")
    summaryStream.WriteLine systemName & " daily check finished: " & Now
    summaryStream.Close

    crt.Dialog.MessageBox "Daily check finished. Log directory:" & vbCrLf & logRoot, "SecureCRT IDC Check"
End Sub

Sub RunCheckForTab(ByRef tabObj, ByVal logRoot, ByRef summaryStream, ByVal systemName, ByVal currentIdx)
    Dim screenObj, logPath, commandList, prompt, deviceName, index, commandText, matchIdx

    If Not IsTabConnected(tabObj) Then
        summaryStream.WriteLine "[" & Now & "] Detection: Attempting Auto-Reconnect for " & tabObj.Caption
        On Error Resume Next
        tabObj.Session.Connect
        crt.Sleep 2000
        On Error GoTo 0
    End If

    If Not IsTabConnected(tabObj) Then
        summaryStream.WriteLine "[" & Now & "] Tab not connected, skip: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    Set screenObj = tabObj.Screen
    screenObj.Synchronous = True
    tabObj.Activate
    screenObj.Send vbCr
    
    matchIdx = screenObj.WaitForStrings(Array(">", "]", "#"), 10)
    If matchIdx = 0 Then
        summaryStream.WriteLine "[" & Now & "] Prompt not detected, skip: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    prompt = Trim(screenObj.Get(screenObj.CurrentRow, 1, screenObj.CurrentRow, screenObj.Columns))
    deviceName = ExtractDeviceNameFromText(GetTabCaptionSafe(tabObj))
    if Len(deviceName) = 0 Then
        deviceName = ExtractDeviceNameFromPrompt(prompt)
    end if
    
    If Len(deviceName) = 0 Then
        summaryStream.WriteLine "[" & Now & "] Device name not detected, skip tab: " & GetTabCaptionSafe(tabObj)
        Exit Sub
    End If

    If g_seenDevices.Exists(deviceName) Then
        summaryStream.WriteLine "[" & Now & "] Skip (duplicate device): " & deviceName
        Exit Sub
    End If
    g_seenDevices.Add deviceName, True

    summaryStream.WriteLine "[" & Now & "] Start tab: " & deviceName & " prompt: " & prompt

    logPath = g_fso.BuildPath(logRoot, systemName & "_" & Replace(deviceName, " ", "_") & "_" & TimeStampForFile(Now) & ".log")
    StartSessionLog tabObj, logPath

    ' 禁用分页并在等待时执行保活
    SendCommandWithStrictPulse screenObj, prompt, "screen-length 0 temporary", currentIdx

    commandList = GetCommandsForSession()
    For index = 0 To UBound(commandList)
        commandText = commandList(index)
        If Len(Trim(commandText)) > 0 Then
            summaryStream.WriteLine "[" & Now & "] " & deviceName & " run command: " & commandText
            If Not SendCommandWithStrictPulse(screenObj, prompt, commandText, currentIdx) Then
                summaryStream.WriteLine "[" & Now & "] " & deviceName & " command timed out: " & commandText
            End If
        End If
    Next

    StopSessionLog tabObj
    summaryStream.WriteLine "[" & Now & "] Tab finished: " & deviceName
End Sub

' 核心：在等待期间进行保活
Function SendCommandWithStrictPulse(ByRef screenObj, ByVal prompt, ByVal cmd, ByVal currentIdx)
    screenObj.Send cmd & vbCr
    Dim matchIndex
    Do
        matchIndex = screenObj.WaitForStrings(Array("---- More ----", "--More--", "Press any key", prompt), 15)
        If matchIndex = 0 Then
            GlobalPulse currentIdx + 1
        ElseIf matchIndex >= 1 And matchIndex <= 3 Then
            screenObj.Send " " 
        ElseIf matchIndex = 4 Then
            SendCommandWithStrictPulse = True
            Exit Function
        End If
    Loop
End Function

Sub GlobalPulse(ByVal startIdx)
    Dim j, pulseTab
    On Error Resume Next
    For j = startIdx To g_tabCount
        Set pulseTab = crt.GetTab(j)
        If Not pulseTab Is Nothing Then If pulseTab.Session.Connected Then pulseTab.Screen.Send vbCr
    Next
    On Error GoTo 0
End Sub

Function GetCommandsForSession()
    GetCommandsForSession = Array("display startup","display device","display alarm all","display alarm urgent","display alarm active","display temperature","display environment","display temperature all","display health","display cpu-usage","display cpu","display memory-usage","display memory","display interface brief","display ip interface brief","display vrrp brief","display vrrp","display current-configuration","display ip routing-table","display logbuffer","display arp all","display arp","display clock","display switchover state","display saved-configuration")
End Function

Function BuildLogRoot(ByVal sysName)
    Dim basePath, dateFolder
    basePath = Left(crt.ScriptFullName, InStrRev(crt.ScriptFullName, "\") - 1)
    dateFolder = Year(Date) & "-" & Month(Date) & "-" & Day(Date)
    BuildLogRoot = g_fso.BuildPath(basePath, "logs\" & dateFolder & "\" & sysName)
End Function

' --- 辅助函数 ---
Function ExtractDeviceNameFromPrompt(ByVal promptText)
    Dim re, matches
    Set re = New RegExp
    re.Global = False
    re.IgnoreCase = True
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
    re.Pattern = "([A-Z0-9_.\s-]{3,60})"
    Set matches = re.Execute(sourceText)
    If matches.Count > 0 Then
        ExtractDeviceNameFromText = UCase(Trim(matches(0).Value))
    Else
        ExtractDeviceNameFromText = ""
    End If
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
    TimeStampForFile = Year(dt) & Right("0"&Month(dt),2) & Right("0"&Day(dt),2) & "_" & Right("0"&Hour(dt),2) & Right("0"&Minute(dt),2) & Right("0"&Second(dt),2)
End Function
