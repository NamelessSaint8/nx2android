---
status: diagnosed
trigger: "Download missing tools loads the download lists and fetches the missing tools from the signed macOS app"
created: 2026-10-30T00:00:00Z
updated: 2026-10-30T05:10:00Z
---

## Current Focus

bug_class: Bohrbug (deterministic: fails every time, on every Mac that lacks python.org 3.14 + Install Certificates)
hypothesis: CONFIRMED. The macOS bundle freezes the python.org framework Python, whose private OpenSSL has OPENSSLDIR baked in as
  /Library/Frameworks/Python.framework/Versions/3.14/etc/openssl. That folder does not exist on a player's Mac, and porter's urlopen calls pass
  no SSL context, so the context loads 0 CA certificates and every HTTPS request fails verification.
test: done (negative repro in the signed bundle, positive control with SSL_CERT_FILE, Linux differential Debian vs Fedora)
expecting: n/a
next_action: none (goal find_root_cause_only); hand the fix direction to plan-phase --gaps

reasoning_checkpoint:
  hypothesis: "The frozen macOS Python looks for CAs only at its build host's python.org path, which is absent on the player's Mac, because the bundled libcrypto's OPENSSLDIR is compiled in and porter supplies no CA source of its own"
  confirming_evidence:
    - "Inside the signed DMG app: get_default_verify_paths() cafile=None capath=None, openssl_cafile=/Library/Frameworks/Python.framework/Versions/3.14/etc/openssl/cert.pem MISSING; 0 CA certs; the exact UAT error"
    - "Same app with SSL_CERT_FILE=/etc/ssl/cert.pem: 128 CA certs, dl.google.com 200 (hardened runtime, Developer ID signature unchanged)"
    - "strings of the bundled libcrypto.3.dylib: OPENSSLDIR \"/Library/Frameworks/Python.framework/Versions/3.14/etc/openssl\""
    - "Linux arm64 bundle, same mechanism (OPENSSLDIR /usr/lib/ssl): Debian trixie 148 certs OK; Fedora 44 0 certs FAIL; Fedora + SSL_CERT_FILE=tls-ca-bundle.pem 146 certs OK"
  falsification_test: "If the app had failed with a CA file supplied, or loaded certificates and still failed, the cause would be elsewhere (proxy, hardened runtime, clock). It succeeded."
  fix_rationale: "Give porter's HTTPS calls a CA source that exists on the player's machine (OS trust store or a shipped bundle) instead of relying on a compile-time path from the CI runner"
  blind_spots: "truststore was not executed inside the signed app or on Fedora (running downloaded code was blocked); the Windows zip was not run (conclusion rests on CPython's load_default_certs reading the Windows ROOT/CA stores); Linux x64 tarball not run on non-Debian (same OPENSSLDIR as the arm64 one, so same prediction)"
  candidate_causes:
    - "environment/build: python.org framework OpenSSL with build-host OPENSSLDIR frozen into the bundle (CONFIRMED)"
    - "code: porter passes no context= / cafile to urlopen, so nothing overrides the empty default (CONFIRMED, contributing)"
    - "config/signing: hardened runtime or missing entitlements blocking keychain/TLS (ELIMINATED)"
    - "environment/network: an intercepting proxy on the tester's network (ELIMINATED)"
  and_gate: "yes: it takes both the frozen build-host CA path AND porter supplying no CA source; either one alone being fixed makes downloads work"

## Symptoms

expected: On the Setup tab of the notarized macOS app, pressing "Download missing tools" loads the download lists and downloads the missing tools (here the Android NDK) into the player's nx2android folder.
actual: User reported: "test passes, but there's an issue downloading the rools" (the Gatekeeper test passed; the download did not).
errors: The Setup tab shows, in red: "porter failed / cannot read the download lists: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1085)>"
reproduction: UAT test 6. d2ec054 DMG from fork-release run 40971470754 (nx2android-d2ec054-macos-arm64.dmg, signed + notarized, hardened runtime), started from /Volumes/nx2android. Setup tab reports Python 3.14.10 at /Volumes/nx2android/nx2android.app/Contents/MacOS/nx2android.
started: Discovered during UAT (first macOS bundle exercised for downloads). Linux x64 tarball (Python 3.14.9) downloads fine on a Debian-family host.

## Eliminated

- hypothesis: The hardened runtime (or missing entitlements) blocks TLS or keychain access in the signed app
  evidence: The same signed app (flags=0x10000(runtime), Developer ID 3PR92LKXFZ) verifies dl.google.com and returns 200 as soon as SSL_CERT_FILE names a CA file. The signature and runtime are not involved; only the CA source is.
  timestamp: 2026-10-30T05:00:00Z

- hypothesis: An intercepting proxy or a network problem on the tester's Mac
  evidence: With Apple's public CA bundle (/etc/ssl/cert.pem) the chain verifies, so the server presents a normal public chain; and the dev venv (Homebrew Python) on the same Mac downloads fine.
  timestamp: 2026-10-30T05:00:00Z

- hypothesis: Something specific to Python 3.14.10 vs 3.14.9 (the Mac and Linux bundles' versions differ)
  evidence: The Linux 3.14.9 bundle fails identically on Fedora 44 (0 certs) and works on Debian; the version is irrelevant, the compiled-in OPENSSLDIR decides.
  timestamp: 2026-10-30T05:05:00Z

## Evidence

- timestamp: 2026-10-30T00:40:00Z
  checked: porter/fetch.py, porter/fpslocker.py; grep certifi/truststore/ssl/SSL_CERT over porter/ gui/ packaging/ requirements*.txt .github/
  found: every HTTPS call is urllib.request.urlopen with no context= (fetch._get, fetch.plan HEAD, fetch._download, fpslocker.fetch). No certifi, truststore, SSL_CERT_FILE or ssl context anywhere. requirements*.txt are hashed uv locks (not unpinned, despite the brief), and none lists certifi or truststore.
  implication: TLS trust comes only from the bundled Python's OpenSSL defaults, i.e. its compile-time OPENSSLDIR.

- timestamp: 2026-10-30T00:45:00Z
  checked: ran scratchpad/tls/probe.py via /Volumes/nx2android/nx2android.app/Contents/MacOS/nx2android (the d2ec054 DMG, script-mode dispatch in packaging/nx2android.py)
  found: Python 3.14.10, OpenSSL 3.5.9. ssl.get_default_verify_paths(): cafile=None, capath=None, openssl_cafile='/Library/Frameworks/Python.framework/Versions/3.14/etc/openssl/cert.pem' (MISSING), openssl_capath='.../3.14/etc/openssl/certs' (MISSING). SSL_CERT_FILE/SSL_CERT_DIR unset. create_default_context() loads 0 CA certs. urlopen of fetch.GOOGLE_INDEX fails with the exact UAT error: CERTIFICATE_VERIFY_FAILED unable to get local issuer certificate (_ssl.c:1085).
  implication: Reproduced outside the GUI. The bundle's OpenSSL looks for CAs at an absolute path on the player's Mac that does not exist.

- timestamp: 2026-10-30T00:47:00Z
  checked: strings of the bundled Contents/Frameworks/libcrypto.3.dylib; otool -L of _ssl.cpython-314-darwin.so; /Library/Frameworks/Python.framework/Versions on this Mac
  found: OPENSSLDIR "/Library/Frameworks/Python.framework/Versions/3.14/etc/openssl" is baked into the bundled libcrypto. _ssl links @rpath/libssl.3.dylib and libcrypto.3.dylib (the bundled copies). This Mac has only Python.framework 3.12; no 3.14.
  implication: The macOS job's actions/setup-python installs the python.org framework build, which ships a private OpenSSL whose CA store is filled only when the user runs "Install Certificates.command" (it symlinks certifi's cacert.pem into that etc/openssl). It never uses the macOS keychain. PyInstaller copies that libcrypto with its build-host path, so on a tester's Mac the store is empty (or, if they happen to have python.org 3.14 installed and ran Install Certificates, it works by accident from a file outside the signed app).

- timestamp: 2026-10-30T00:48:00Z
  checked: the dev venv's Python on this Mac (.venv/bin/python)
  found: Homebrew Python 3.14.5, OpenSSL 3.6.3, cafile='/opt/homebrew/etc/openssl@3/cert.pem' (populated by Homebrew's ca-certificates).
  implication: Explains why dev runs (python -m gui / -m porter) download fine on the same Mac: the dev interpreter has a populated store; only the frozen python.org build has none.

- timestamp: 2026-10-30T00:50:00Z
  checked: _pyinstaller_hooks_contrib (2026.9) hooks for certifi/ssl; PyInstaller 6.22.3
  found: hook-certifi.py only collects certifi's data files; there is no runtime hook that sets SSL_CERT_FILE, and none for ssl at all.
  implication: Bundling certifi alone would not fix it; porter must pass the CA file (or a truststore context) itself.

- timestamp: 2026-10-30T00:52:00Z
  checked: Linux x64 tarball from the same run (gh run download, nx2android-d2ec054-linux-x64.tar.gz), strings of _internal/libcrypto.so.3
  found: the bundle carries its own libssl.so.3 + libcrypto.so.3 (Ubuntu 22.04's OpenSSL 3.0.2) with OPENSSLDIR "/usr/lib/ssl" (cert.pem, certs/).
  implication: Same mechanism as macOS: the build host's CA path is baked in. It works on the Debian-family tester host because Debian/Ubuntu have /usr/lib/ssl/certs -> /etc/ssl/certs. Distros without /usr/lib/ssl (Fedora/RHEL use /etc/pki/tls, Arch uses /etc/ssl) are predicted to fail the same way.

- timestamp: 2026-10-30T05:00:00Z
  checked: positive control, the same signed app with SSL_CERT_FILE=/etc/ssl/cert.pem (Apple's system PEM bundle); codesign -dv of the app
  found: 128 CA certs loaded, dl.google.com repository2-3.xml returns 200. codesign: flags=0x10000(runtime), Authority=Developer ID Application (3PR92LKXFZ).
  implication: Root cause confirmed. Supplying any existing CA source fixes it under the hardened runtime with no entitlement change.

- timestamp: 2026-10-30T05:02:00Z
  checked: Linux arm64 tarball from the same run (Ubuntu 24.04 OpenSSL 3.0.13, OPENSSLDIR "/usr/lib/ssl"), run in containers with scratchpad/tls/probe.py
  found: Fedora 44 (glibc 2.43, ca-certificates installed, no /usr/lib/ssl): 0 certs, same CERTIFICATE_VERIFY_FAILED. Fedora 44 + SSL_CERT_FILE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem: 146 certs, 200. Debian trixie + ca-certificates: /usr/lib/ssl/cert.pem -> /etc/ssl/certs/ca-certificates.crt, 148 certs, 200. (Fedora 44 no longer has /etc/pki/tls/certs/ca-bundle.crt.)
  implication: Linux bundles share the bug on every distro without Debian's /usr/lib/ssl layout (Fedora, RHEL, Arch, openSUSE). The UAT Linux pass was on a Debian-family host only.

- timestamp: 2026-10-30T05:04:00Z
  checked: CPython ssl.SSLContext.load_default_certs (what urlopen's default context calls)
  found: on win32 it loads the Windows ROOT and CA system stores before set_default_verify_paths().
  implication: The Windows zip uses the OS trust store and does not share this bug (not run). The caveat is Windows' on-demand root update: a root Windows has never fetched is not in the store; dl.google.com and Microsoft's roots are effectively always present.

- timestamp: 2026-10-30T05:06:00Z
  checked: porter/pipeline.py fps_unlock stage (line ~244) around fpslocker.fetch
  found: URLError is an OSError, so the stage catches it and prints '[RED] 60 fps: ... could not be fetched (...): the game keeps its own frame rate'.
  implication: A second user-visible effect in the macOS bundle (and on non-Debian Linux): --fps60 ports silently stay at the game's own frame rate. Any fix must cover fpslocker.fetch too, not only fetch.py.

- timestamp: 2026-10-30T05:08:00Z
  checked: truststore 0.10.5 wheel source (read only, not executed), truststore/_openssl.py
  found: on Linux it calls set_default_verify_paths() only when OpenSSL's defaults point at real certs, else loads the first existing of /etc/ssl/cert.pem, /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem (Fedora 44+), /etc/pki/tls/cert.pem, /etc/ssl/certs/ca-certificates.crt, /etc/ssl/ca-bundle.pem. On macOS and Windows it verifies through Security.framework / CertGetCertificateChain via ctypes.
  implication: truststore covers all three OSes including the Fedora 44 layout. Not run inside the signed app (running downloaded code was blocked), so its ctypes use under the hardened runtime is still unverified.

## Resolution

root_cause: The bundles freeze CI's Python together with its OpenSSL, and that OpenSSL's CA location is a compile-time path on the build host. On macOS that is the python.org framework's /Library/Frameworks/Python.framework/Versions/3.14/etc/openssl, which exists on a player's Mac only if they installed python.org 3.14 and ran Install Certificates.command; on Linux it is Ubuntu's /usr/lib/ssl, which only Debian-family hosts have; porter's urlopen calls (porter/fetch.py _get, plan HEAD, _download; porter/fpslocker.py fetch) pass no SSL context or CA file, so nothing replaces the empty default and every HTTPS request fails with CERTIFICATE_VERIFY_FAILED (unable to get local issuer certificate)
fix: (not applied; goal find_root_cause_only) see the fix directions in the return report
verification: n/a
files_changed: []
