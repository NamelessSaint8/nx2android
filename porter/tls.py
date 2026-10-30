# The one SSL context every HTTPS call in porter/ passes as context= (fetch.py's lists and archives, fpslocker.py's configs).
# The bundles freeze the CI runner's OpenSSL, whose CA location is a path on that runner: python.org's /Library/Frameworks/Python.framework/Versions/3.14/etc/openssl
# on macOS, Ubuntu's /usr/lib/ssl on Linux. On a player's Mac or a Fedora, Arch or openSUSE host that loads no CA and every download fails with CERTIFICATE_VERIFY_FAILED
# (UAT G-01-6, reproduced from the signed DMG, which verifies dl.google.com once given Apple's /etc/ssl/cert.pem). A context, not SSL_CERT_FILE for the whole process:
# that would reach dotnet, whose NuGet restore on Linux honours it, and clang, adb and the porter children.
import os, ssl

CA_FILES = (
    '/etc/ssl/cert.pem',                                   # macOS, Arch, Alpine
    # shortcut: /etc/ssl/cert.pem is Apple's system root bundle, not the keychain, so a root that only an admin added to the keychain (a TLS-inspecting proxy)
    # is not trusted; the player can name a CA file with SSL_CERT_FILE; read the keychain (truststore) when a tester needs that.
    '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem',   # Fedora 44+, RHEL
    '/etc/pki/tls/cert.pem',                               # older Fedora and RHEL
    '/etc/ssl/certs/ca-certificates.crt',                  # Debian, Ubuntu
    '/etc/ssl/ca-bundle.pem',                              # openSUSE
)   # truststore 0.10.5's order


def context(ca_files=CA_FILES):
    """The default context, with the first host CA file loaded when the default store holds no CA; it always verifies"""
    c = ssl.create_default_context()
    if c.cert_store_stats()['x509_ca']: return c   # Windows' system stores, Debian's /usr/lib/ssl, a dev Python, the player's SSL_CERT_FILE
    p = next((p for p in ca_files if os.path.isfile(p)), None)
    if p: c.load_verify_locations(cafile=p)
    return c   # no host file: still CERT_REQUIRED, so the download fails with its own message rather than going unverified
