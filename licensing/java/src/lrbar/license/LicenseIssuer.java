package lrbar.license;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.SecureRandom;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;

/**
 * Builds the same Ed25519-signed license tokens as the Python issuer:
 *
 * <pre>LRBG1.&lt;base64url(payload)&gt;.&lt;base64url(signature)&gt;</pre>
 *
 * The payload is sorted the same way Python's {@code json.dumps(sort_keys=True)}
 * writes it, so keys produced here are byte-for-byte compatible with the app's
 * verifier.
 */
public final class LicenseIssuer {

    public static final String KEY_PREFIX = "LRBG1";
    public static final int KEY_VERSION = 1;
    public static final int DAY_SECONDS = 24 * 60 * 60;
    public static final int DEFAULT_VIDEOS = 2;
    public static final String DAY = "day";
    public static final String LIFETIME = "lifetime";

    private static final SecureRandom RANDOM = new SecureRandom();

    private LicenseIssuer() {
    }

    /** Result of issuing one key. */
    public static final class Issued {
        public final String key;
        public final String licenseId;
        public final long issuedAt;
        public final long expiresAt;
        public final int videos;

        Issued(String key, String licenseId, long issuedAt, long expiresAt,
               int videos) {
            this.key = key;
            this.licenseId = licenseId;
            this.issuedAt = issuedAt;
            this.expiresAt = expiresAt;
            this.videos = videos;
        }
    }

    public static boolean isKnownType(String kind) {
        return DAY.equals(kind) || LIFETIME.equals(kind);
    }

    public static Issued issue(Path privateKeyFile, String machineId, String kind,
                               int days, int videos, String note) throws IOException {
        String machine = MachineId.normalize(machineId);
        if (machine.isEmpty()) {
            throw new IllegalArgumentException(
                    "Machine ID must be 20 hexadecimal characters, for example "
                            + "7F3A-9C2E-1B44-D07A-55C1.\n\n"
                            + "Ask the customer to copy it from the activation "
                            + "window (Copy ID button).");
        }
        if (!isKnownType(kind)) {
            throw new IllegalArgumentException(
                    "License type must be 'day' or 'lifetime'.");
        }

        boolean lifetime = LIFETIME.equals(kind);
        long issued = Instant.now().getEpochSecond();
        long expires = lifetime ? 0 : issued + Math.max(1, days) * DAY_SECONDS;
        int maxVideos = lifetime ? 0 : Math.max(1, videos);
        String licenseId = randomHex(4);
        String safeNote = note == null ? "" : note.trim();
        if (safeNote.length() > 120) {
            safeNote = safeNote.substring(0, 120);
        }

        // Key order matches json.dumps(payload, sort_keys=True): e, i, m, n,
        // note, r, t, v.
        String payload = "{"
                + "\"e\":" + expires + ","
                + "\"i\":" + issued + ","
                + "\"m\":" + Json.quote(machine) + ","
                + "\"n\":" + maxVideos + ","
                + "\"note\":" + Json.quote(safeNote) + ","
                + "\"r\":" + Json.quote(licenseId) + ","
                + "\"t\":" + Json.quote(kind) + ","
                + "\"v\":" + KEY_VERSION
                + "}";

        String signed = KEY_PREFIX + "."
                + base64Url(payload.getBytes(StandardCharsets.UTF_8));
        PrivateKey privateKey = loadPrivateKey(privateKeyFile);
        String signature;
        try {
            Signature signer = Signature.getInstance("Ed25519");
            signer.initSign(privateKey);
            signer.update(signed.getBytes(StandardCharsets.US_ASCII));
            signature = base64Url(signer.sign());
        } catch (java.security.GeneralSecurityException ex) {
            throw new IOException(
                    "Ed25519 signing is not available in this Java runtime. "
                            + "Use Java 17 or newer. (" + ex.getMessage() + ")", ex);
        }

        return new Issued(signed + "." + signature, licenseId, issued, expires,
                maxVideos);
    }

    public static PrivateKey loadPrivateKey(Path file) throws IOException {
        if (file == null || !Files.isRegularFile(file)) {
            throw new IOException(
                    "Private key not found:\n" + file
                            + "\n\nKeep private_key.pem in the licensing folder "
                            + "(or restore your backup).");
        }
        String pem = Files.readString(file, StandardCharsets.UTF_8);
        if (pem.contains("ENCRYPTED PRIVATE KEY")) {
            throw new IOException(
                    "The private key is password-protected. This tool expects the "
                            + "unencrypted private_key.pem created by keygen.py.");
        }
        String base64 = pem
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s", "");
        try {
            byte[] der = Base64.getDecoder().decode(base64);
            KeyFactory factory = KeyFactory.getInstance("Ed25519");
            return factory.generatePrivate(new PKCS8EncodedKeySpec(der));
        } catch (IllegalArgumentException | java.security.GeneralSecurityException ex) {
            throw new IOException(
                    "Could not read the private key. It may be damaged or not an "
                            + "Ed25519 PKCS#8 PEM file. (" + ex.getMessage() + ")", ex);
        }
    }

    private static String base64Url(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private static String randomHex(int bytes) {
        byte[] raw = new byte[bytes];
        RANDOM.nextBytes(raw);
        StringBuilder out = new StringBuilder(bytes * 2);
        for (byte b : raw) {
            out.append(String.format("%02x", b));
        }
        return out.toString();
    }
}
