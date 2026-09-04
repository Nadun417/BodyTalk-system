# Prepares this computer to analyse videos.
#
# BodyTalk is two programs. The window you click on is one of them, and it is installed with
# the application. The part that actually looks at a video is written in Python, because that
# is where the body-tracking library lives, and Python is not something an installer can
# reasonably carry: the library alone is several hundred megabytes and it needs a matching
# version of Python underneath it.
#
# So the application ships the analysis code and this script fetches the rest. Run it once,
# after installing, and everything works from then on. Until it has been run the application
# still opens, and old sessions can still be read, but analysing a new video will say plainly
# that the analysis software is missing.
#
# Run it by right-clicking this file and choosing "Run with PowerShell", or from a terminal:
#
#     powershell -ExecutionPolicy Bypass -File setup.ps1
#
# It is safe to run more than once. If everything is already in place it checks and says so
# rather than downloading anything again.

# Deliberately not set to stop on errors. This script's whole job is driving other programs,
# and those write ordinary progress and warnings to the error stream as they go. Treating that
# as a failure stops the script in the middle of work that was going fine. Every step below
# checks the exit code of what it ran instead, which is what actually says whether it worked.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $here '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'
$requirements = Join-Path $here 'requirements.txt'

function Test-Ready {
    # Ready means the environment exists and the body-tracking library actually loads in it.
    # Checking that it loads matters more than checking that the folder is there: a half
    # finished install leaves the folder behind and would otherwise look finished.
    if (-not (Test-Path $venvPython)) { return $false }
    & $venvPython -c "import mediapipe, cv2, numpy" 2>$null
    return ($LASTEXITCODE -eq 0)
}

Write-Host ''
Write-Host 'BodyTalk - preparing video analysis' -ForegroundColor Cyan
Write-Host ''

if (Test-Ready) {
    Write-Host 'Everything is already in place. You can analyse videos.' -ForegroundColor Green
    Write-Host ''
    exit 0
}

# The body-tracking library does not publish builds for every version of Python, so a suitable
# one has to be found rather than assumed. The newest Python on a machine is usually too new
# for it, which is a baffling failure if it is not headed off here.
#
# The launcher is asked what is installed, rather than each version being tried in turn. Trying
# them in turn looks simpler and is worse: asking for a version that is not there is itself an
# error, and the first miss would end the search before the version that IS present got its
# turn. That is not a hypothetical. The machine this was written on has 3.11 and 3.14, the
# search asked for 3.12 first, and the script stopped without ever trying the 3.11 sitting
# right there.
$python = $null
$listing = & py -0p 2>&1
if ($LASTEXITCODE -eq 0) {
    foreach ($version in @('3.12', '3.11')) {
        foreach ($line in $listing) {
            # Lines look like " -V:3.11          C:\path	o\python.exe". The "t" suffixed
            # builds are a different, experimental flavour of Python and are skipped.
            if ("$line" -match "^\s*-V:$([regex]::Escape($version))\s+\*?\s*(?<path>.+\.exe)\s*$") {
                $python = $Matches['path'].Trim()
                break
            }
        }
        if ($python) { break }
    }
}

# If the launcher is not installed, fall back to whatever "python" means on this machine, but
# only if it turns out to be a version the library supports.
if (-not $python) {
    $version = & python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1
    if ($LASTEXITCODE -eq 0 -and ("$version".Trim() -in @('3.11', '3.12'))) {
        $python = (& python -c "import sys; print(sys.executable)" 2>&1).Trim()
    }
}

if (-not $python) {
    Write-Host 'Python 3.11 or 3.12 is needed and neither was found on this computer.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'Install one from python.org, tick "Add python.exe to PATH" during the install,'
    Write-Host 'then run this script again. Newer versions such as 3.13 or 3.14 will not work:'
    Write-Host 'the body-tracking library does not publish builds for them yet.'
    Write-Host ''
    exit 1
}

Write-Host "Using $python"
Write-Host 'Creating the environment. This takes a few minutes and downloads about 300 MB.'
Write-Host ''

& $python -m venv $venv
if ($LASTEXITCODE -ne 0) { Write-Host 'Could not create the environment.' -ForegroundColor Red; exit 1 }

& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host 'The download did not finish. Check the internet connection and run this again.' -ForegroundColor Red
    Write-Host 'Nothing is lost by running it a second time.'
    exit 1
}

Write-Host ''
if (Test-Ready) {
    Write-Host 'Done. BodyTalk can now analyse videos.' -ForegroundColor Green
    Write-Host 'This is the only time anything is downloaded. The app itself never uses the internet.'
} else {
    Write-Host 'The install finished but the library still will not load.' -ForegroundColor Red
    Write-Host 'Running this script again usually clears it up.'
    exit 1
}
Write-Host ''
