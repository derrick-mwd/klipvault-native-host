/**
 * ClipVault Firefox Native Host Wrapper (Windows)
 *
 * Firefox on Windows requires native messaging hosts to be actual .exe files.
 * .bat files don't work because Firefox uses CreateProcessW directly.
 *
 * This tiny wrapper:
 *  1. Finds its own directory
 *  2. Discovers python.exe via Windows registry (no env vars needed)
 *  3. Runs "python.exe clipvault_host.py" with inherited stdio handles
 *  4. Waits for the child to finish
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define MAX_STR 4096

/**
 * Find python.exe by reading the Windows registry.
 * Tries HKLM\SOFTWARE\Python\PythonCore\<ver>\InstallPath first,
 * then HKCU, then falls back to PATH search.
 */
static int find_python(char *out, size_t out_size) {
    HKEY hKey;
    char path[MAX_STR];
    DWORD path_len = sizeof(path);
    LONG ret;

    // Try HKLM first (system-wide Python installs)
    const char *versions[] = {"3.13", "3.12", "3.11", "3.10", "3.9", "3.8"};
    for (size_t i = 0; i < sizeof(versions)/sizeof(versions[0]); i++) {
        char keyPath[MAX_STR];
        snprintf(keyPath, sizeof(keyPath),
                 "SOFTWARE\\Python\\PythonCore\\%s\\InstallPath", versions[i]);

        ret = RegOpenKeyExA(HKEY_LOCAL_MACHINE, keyPath, 0, KEY_QUERY_VALUE, &hKey);
        if (ret == ERROR_SUCCESS) {
            path_len = sizeof(path);
            ret = RegQueryValueExA(hKey, "ExecutablePath", NULL, NULL,
                                   (LPBYTE)path, &path_len);
            if (ret == ERROR_SUCCESS && path_len > 1) {
                RegCloseKey(hKey);
                snprintf(out, out_size, "%s", path);
                return 0;
            }
            // Fallback: read default value (install dir) and append python.exe
            path_len = sizeof(path);
            ret = RegQueryValueExA(hKey, NULL, NULL, NULL,
                                   (LPBYTE)path, &path_len);
            if (ret == ERROR_SUCCESS && path_len > 1) {
                RegCloseKey(hKey);
                // path already contains trailing backslash sometimes
                size_t len = strlen(path);
                if (len > 0 && (path[len-1] == '\\' || path[len-1] == '/')) {
                    snprintf(out, out_size, "%spython.exe", path);
                } else {
                    snprintf(out, out_size, "%s\\python.exe", path);
                }
                return 0;
            }
            RegCloseKey(hKey);
        }
    }

    // Try HKCU (user installs)
    for (size_t i = 0; i < sizeof(versions)/sizeof(versions[0]); i++) {
        char keyPath[MAX_STR];
        snprintf(keyPath, sizeof(keyPath),
                 "SOFTWARE\\Python\\PythonCore\\%s\\InstallPath", versions[i]);

        ret = RegOpenKeyExA(HKEY_CURRENT_USER, keyPath, 0, KEY_QUERY_VALUE, &hKey);
        if (ret == ERROR_SUCCESS) {
            path_len = sizeof(path);
            ret = RegQueryValueExA(hKey, "ExecutablePath", NULL, NULL,
                                   (LPBYTE)path, &path_len);
            if (ret == ERROR_SUCCESS && path_len > 1) {
                RegCloseKey(hKey);
                snprintf(out, out_size, "%s", path);
                return 0;
            }
            path_len = sizeof(path);
            ret = RegQueryValueExA(hKey, NULL, NULL, NULL,
                                   (LPBYTE)path, &path_len);
            if (ret == ERROR_SUCCESS && path_len > 1) {
                RegCloseKey(hKey);
                size_t len = strlen(path);
                if (len > 0 && (path[len-1] == '\\' || path[len-1] == '/')) {
                    snprintf(out, out_size, "%spython.exe", path);
                } else {
                    snprintf(out, out_size, "%s\\python.exe", path);
                }
                return 0;
            }
            RegCloseKey(hKey);
        }
    }

    // Final fallback: hope python.exe is in PATH or same dir
    snprintf(out, out_size, "python.exe");
    return -1;
}

int main(void) {
    char exeDir[MAX_STR];
    char pyScript[MAX_STR];
    char pythonExe[MAX_STR];

    // Get directory of this executable
    DWORD len = GetModuleFileNameA(NULL, exeDir, sizeof(exeDir));
    if (len == 0 || len >= sizeof(exeDir)) {
        fprintf(stderr, "[ClipVaultWrapper] Failed to get module path\n");
        return 1;
    }

    char *lastSlash = strrchr(exeDir, '\\');
    if (!lastSlash) lastSlash = strrchr(exeDir, '/');
    if (lastSlash) *(lastSlash + 1) = '\0';

    // Build path to clipvault_host.py
    snprintf(pyScript, sizeof(pyScript), "%sclipvault_host.py", exeDir);

    // Verify the script exists
    DWORD attrs = GetFileAttributesA(pyScript);
    if (attrs == INVALID_FILE_ATTRIBUTES) {
        fprintf(stderr, "[ClipVaultWrapper] clipvault_host.py not found: %s\n", pyScript);
        return 1;
    }

    // Find python.exe
    find_python(pythonExe, sizeof(pythonExe));

    // Build command line
    char cmdLine[MAX_STR * 2];
    snprintf(cmdLine, sizeof(cmdLine), "\"%s\" \"%s\"", pythonExe, pyScript);

    // Prepare STARTUPINFO to inherit stdio handles
    STARTUPINFOA si = {0};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput  = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdError  = GetStdHandle(STD_ERROR_HANDLE);

    PROCESS_INFORMATION pi = {0};

    // Create the Python process, inheriting our stdio handles
    BOOL created = CreateProcessA(
        NULL,           // Application name (use cmdLine)
        cmdLine,        // Command line
        NULL,           // Process security attributes
        NULL,           // Thread security attributes
        TRUE,           // Inherit handles
        0,              // Creation flags
        NULL,           // Environment
        NULL,           // Current directory
        &si,
        &pi
    );

    if (!created) {
        DWORD err = GetLastError();
        fprintf(stderr, "[ClipVaultWrapper] CreateProcess failed (error %lu)\n", err);
        fprintf(stderr, "[ClipVaultWrapper] Command: %s\n", cmdLine);
        return 1;
    }

    // Wait for Python to finish (Firefox will close stdin when done)
    WaitForSingleObject(pi.hProcess, INFINITE);

    DWORD exitCode = 1;
    GetExitCodeProcess(pi.hProcess, &exitCode);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return (int)exitCode;
}
