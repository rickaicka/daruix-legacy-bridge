Attribute VB_Name = "ExportarRM"
Option Compare Database
Option Explicit

' Executar no FRONT-END que contém o formulário, não no backend de tabelas.
' Exporta definições e código; não abre formulários nem executa consultas.
Public Sub ExportarEstruturaRM()
    Dim pasta As String, arquivo As Integer, db As Object, q As Object
    Dim obj As AccessObject, texto As String, n As Long, destino As String
    pasta = CurrentProject.Path & "\RM_estrutura_" & Format(Now, "yyyymmdd_hhnnss")
    MkDir pasta
    Set db = CurrentDb
    arquivo = FreeFile
    Open pasta & "\inventario.txt" For Output As #arquivo
    Print #arquivo, "FORMULARIOS"
    For Each obj In CurrentProject.AllForms
        Print #arquivo, obj.Name
    Next obj
    Print #arquivo, vbCrLf & "RELATORIOS"
    For Each obj In CurrentProject.AllReports
        Print #arquivo, obj.Name
    Next obj
    Print #arquivo, vbCrLf & "MODULOS"
    For Each obj In CurrentProject.AllModules
        Print #arquivo, obj.Name
    Next obj
    Print #arquivo, vbCrLf & "MACROS"
    For Each obj In CurrentProject.AllMacros
        Print #arquivo, obj.Name
    Next obj
    Close #arquivo
    arquivo = FreeFile
    Open pasta & "\consultas.sql.txt" For Output As #arquivo
    For Each q In db.QueryDefs
        Print #arquivo, "-- CONSULTA: " & q.Name
        Print #arquivo, q.SQL
        Print #arquivo, vbCrLf
    Next q
    Close #arquivo
    arquivo = FreeFile
    Open pasta & "\inventario.txt" For Append As #arquivo
    Print #arquivo, vbCrLf & "ARQUIVOS EXPORTADOS"
    ' Todas as definições: subforms/helpers podem não conter RM no nome.
    For Each obj In CurrentProject.AllForms
        n = n + 1
        destino = "form_" & Format(n, "0000") & ".txt"
        Application.SaveAsText acForm, obj.Name, pasta & "\" & destino
        Print #arquivo, destino & " = " & obj.Name
    Next obj
    For Each obj In CurrentProject.AllReports
        n = n + 1
        destino = "report_" & Format(n, "0000") & ".txt"
        Application.SaveAsText acReport, obj.Name, pasta & "\" & destino
        Print #arquivo, destino & " = " & obj.Name
    Next obj
    For Each obj In CurrentProject.AllModules
        n = n + 1
        destino = "module_" & Format(n, "0000") & ".txt"
        Application.SaveAsText acModule, obj.Name, pasta & "\" & destino
        Print #arquivo, destino & " = " & obj.Name
    Next obj
    For Each obj In CurrentProject.AllMacros
        n = n + 1
        destino = "macro_" & Format(n, "0000") & ".txt"
        Application.SaveAsText acMacro, obj.Name, pasta & "\" & destino
        Print #arquivo, destino & " = " & obj.Name
    Next obj
    Close #arquivo
    MsgBox "Estrutura exportada para: " & pasta, vbInformation
End Sub

