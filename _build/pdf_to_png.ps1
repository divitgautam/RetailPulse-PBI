# Renders each page of a PDF to PNG using the Windows.Data.Pdf API (Windows 10+). Run with Windows PowerShell 5.1.
# Usage: powershell -NoProfile -File _build\pdf_to_png.ps1 <pdf> <outDir> <name1,name2,...> [widthPx]
param([string]$Pdf, [string]$OutDir, [string[]]$Names, [int]$Width = 1920)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
$asTaskAction = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' } | Select-Object -First 1
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(); $task.Result }
function AwaitAction($op) { $asTaskAction.Invoke($null, @($op)).Wait() }

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $Pdf).Path)) ([Windows.Storage.StorageFile])
$doc = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
$names = @($Names | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
for ($i = 0; $i -lt $doc.PageCount; $i++) {
    $page = $doc.GetPage($i)
    $opts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $opts.DestinationWidth = $Width
    $opts.DestinationHeight = [uint32]([math]::Round($Width * $page.Size.Height / $page.Size.Width))
    $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    AwaitAction ($page.RenderToStreamAsync($stream, $opts))
    $name = if ($i -lt $names.Count) { $names[$i] } else { "page_$($i + 1)" }
    $out = Join-Path $OutDir "$name.png"
    $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream.GetInputStreamAt(0))
    $fs = [System.IO.File]::Create($out); $net.CopyTo($fs); $fs.Close()
    "$out  ($($opts.DestinationWidth)x$($opts.DestinationHeight))"
}
"pages: $($doc.PageCount)"
