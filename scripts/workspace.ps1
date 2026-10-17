# Dot-source from PowerShell: . .\scripts\workspace.ps1
# Configures only this process. No separation, conversion, training, or download.

$CoverProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

function Assert-CoverPlainPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $coverCheckPath = [System.IO.Path]::GetFullPath($Path)
    while ($coverCheckPath) {
        $coverItem = $null
        try {
            $coverItem = Get-Item -LiteralPath $coverCheckPath -Force -ErrorAction Stop
        } catch {
            if ($_.CategoryInfo.Category -ne [System.Management.Automation.ErrorCategory]::ObjectNotFound) { throw }
        }
        if ($null -ne $coverItem) {
            if ($coverItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                throw "Links and junctions are not allowed in workspace paths: $coverCheckPath"
            }
        }
        $coverParent = [System.IO.Directory]::GetParent($coverCheckPath)
        if ($null -eq $coverParent) { break }
        $coverCheckPath = $coverParent.FullName
    }
}

function Get-CoverWorkspacePath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $coverResolved = [System.IO.Path]::GetFullPath((Join-Path $CoverProjectRoot $RelativePath))
    if (-not $coverResolved.StartsWith($CoverProjectRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside this project: $coverResolved"
    }
    Assert-CoverPlainPath -Path $coverResolved
    return $coverResolved
}

Assert-CoverPlainPath -Path $CoverProjectRoot
Set-Location -LiteralPath $CoverProjectRoot -ErrorAction Stop

$coverFolders = @(
    '.tmp', '.cache', 'data/source', 'data/separated', 'data/dereverb',
    'data/candidates', 'data/approved', 'data/converted', 'models', 'outputs', 'logs', 'runs'
)
foreach ($coverFolder in $coverFolders) {
    $coverFolderPath = Get-CoverWorkspacePath -RelativePath $coverFolder
    [System.IO.Directory]::CreateDirectory($coverFolderPath) | Out-Null
}

$coverEnvironment = @{
    TEMP = '.tmp'
    TMP = '.tmp'
    PIP_CACHE_DIR = '.cache/pip'
    PYTHONPYCACHEPREFIX = '.cache/pycache'
    PYTHONUSERBASE = '.cache/python_userbase'
    XDG_CACHE_HOME = '.cache'
    HF_HOME = '.cache/huggingface'
    TORCH_HOME = '.cache/torch'
    CUDA_CACHE_PATH = '.cache/cuda'
    NUMBA_CACHE_DIR = '.cache/numba'
    MPLCONFIGDIR = '.cache/matplotlib'
    PYTORCH_KERNEL_CACHE_PATH = '.cache/torch_kernels'
    TORCHINDUCTOR_CACHE_DIR = '.cache/torchinductor'
    TORCH_EXTENSIONS_DIR = '.cache/torch_extensions'
    TRITON_CACHE_DIR = '.cache/triton'
}
foreach ($coverEnvironmentName in $coverEnvironment.Keys) {
    $coverEnvironmentPath = Get-CoverWorkspacePath -RelativePath $coverEnvironment[$coverEnvironmentName]
    [System.IO.Directory]::CreateDirectory($coverEnvironmentPath) | Out-Null
    [System.Environment]::SetEnvironmentVariable($coverEnvironmentName, $coverEnvironmentPath, 'Process')
}
$env:PYTHONUTF8 = '1'
$env:PYTHONNOUSERSITE = '1'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:PIP_NO_INPUT = '1'
$env:PIP_CONFIG_FILE = 'NUL'

$coverLocalFfmpeg = Get-CoverWorkspacePath -RelativePath 'tools/ffmpeg/bin'
if (Test-Path -LiteralPath $coverLocalFfmpeg -PathType Container) {
    $env:Path = $coverLocalFfmpeg + [System.IO.Path]::PathSeparator + $env:Path
}

Write-Host "Workspace ready: $CoverProjectRoot"
Write-Host 'Use .\.venv\Scripts\python.exe explicitly after creating the local virtual environment.'
