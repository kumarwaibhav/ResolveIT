# Stops only the ResolveIT showcase: whatever listens on 127.0.0.1:3000 (web) and :8000 (API),
# plus their gpu_guard parents. Docker Postgres keeps its data; pass -Database to stop it too.
param([switch]$Database)
$ErrorActionPreference = 'Continue'
foreach ($port in 3000, 8000) {
    $owners = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($id in $owners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$id"
        if ($proc -and ($proc.Name -in 'python.exe', 'node.exe')) {
            $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)"
            Stop-Process -Id $id -Force
            if ($parent -and $parent.CommandLine -like '*gpu_guard.py*') { Stop-Process -Id $parent.ProcessId -Force }
            "stopped port $port (pid $id)"
        } elseif ($proc) {
            "port $port is held by $($proc.Name) (pid $id); not ResolveIT, left running"
        }
    }
}
if ($Database) {
    docker ps --filter "publish=54329" --format "{{.Names}}" | ForEach-Object { docker stop $_ | Out-Null; "stopped database container $_" }
}
"ResolveIT showcase stopped."
