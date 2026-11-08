package lrbar.license;

import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Machine IDs are 20 hexadecimal characters grouped in blocks of four, e.g.
 * {@code 7F3A-9C2E-1B44-D07A-55C1}. The seller receives them from the app's
 * activation window, often with spaces or different dashes, so every input is
 * normalized before it is signed into a license.
 */
public final class MachineId {

    private static final Pattern NON_HEX = Pattern.compile("[^0-9A-Fa-f]");

    private MachineId() {
    }

    /** Return the canonical form, or an empty string when the input is invalid. */
    public static String normalize(String input) {
        if (input == null) {
            return "";
        }
        String raw = NON_HEX.matcher(input).replaceAll("").toUpperCase(Locale.ROOT);
        if (raw.length() != 20) {
            return "";
        }
        StringBuilder out = new StringBuilder(24);
        for (int i = 0; i < raw.length(); i += 4) {
            if (i > 0) {
                out.append('-');
            }
            out.append(raw, i, i + 4);
        }
        return out.toString();
    }

    public static boolean isValid(String input) {
        return !normalize(input).isEmpty();
    }
}
