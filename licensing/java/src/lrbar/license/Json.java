package lrbar.license;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Minimal JSON reader/writer so the tool has no external dependencies.
 *
 * <p>Only what the records file needs is supported: objects, arrays, strings,
 * integral and decimal numbers, booleans and null.</p>
 */
final class Json {

    private final String text;
    private int pos;

    private Json(String text) {
        this.text = text;
    }

    static Object parse(String text) {
        Json parser = new Json(text);
        parser.skipWhitespace();
        Object value = parser.parseValue();
        parser.skipWhitespace();
        if (parser.pos != text.length()) {
            throw parser.error("Unexpected trailing data");
        }
        return value;
    }

    /** Quote and escape a string for JSON output. */
    static String quote(String value) {
        String safe = value == null ? "" : value;
        StringBuilder out = new StringBuilder(safe.length() + 2);
        out.append('"');
        for (int i = 0; i < safe.length(); i++) {
            char c = safe.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        out.append('"');
        return out.toString();
    }

    private Object parseValue() {
        skipWhitespace();
        if (pos >= text.length()) {
            throw error("Unexpected end of data");
        }
        char c = text.charAt(pos);
        return switch (c) {
            case '{' -> parseObject();
            case '[' -> parseArray();
            case '"' -> parseString();
            case 't' -> parseLiteral("true", Boolean.TRUE);
            case 'f' -> parseLiteral("false", Boolean.FALSE);
            case 'n' -> parseLiteral("null", null);
            default -> {
                if (c == '-' || (c >= '0' && c <= '9')) {
                    yield parseNumber();
                }
                throw error("Unexpected character '" + c + "'");
            }
        };
    }

    private Map<String, Object> parseObject() {
        expect('{');
        Map<String, Object> object = new LinkedHashMap<>();
        skipWhitespace();
        if (peek() == '}') {
            pos++;
            return object;
        }
        while (true) {
            skipWhitespace();
            String key = parseString();
            skipWhitespace();
            expect(':');
            object.put(key, parseValue());
            skipWhitespace();
            char c = next();
            if (c == '}') {
                return object;
            }
            if (c != ',') {
                throw error("Expected ',' or '}'");
            }
        }
    }

    private List<Object> parseArray() {
        expect('[');
        List<Object> array = new ArrayList<>();
        skipWhitespace();
        if (peek() == ']') {
            pos++;
            return array;
        }
        while (true) {
            array.add(parseValue());
            skipWhitespace();
            char c = next();
            if (c == ']') {
                return array;
            }
            if (c != ',') {
                throw error("Expected ',' or ']'");
            }
        }
    }

    private String parseString() {
        expect('"');
        StringBuilder out = new StringBuilder();
        while (pos < text.length()) {
            char c = text.charAt(pos++);
            if (c == '"') {
                return out.toString();
            }
            if (c != '\\') {
                out.append(c);
                continue;
            }
            char escape = next();
            switch (escape) {
                case '"' -> out.append('"');
                case '\\' -> out.append('\\');
                case '/' -> out.append('/');
                case 'b' -> out.append('\b');
                case 'f' -> out.append('\f');
                case 'n' -> out.append('\n');
                case 'r' -> out.append('\r');
                case 't' -> out.append('\t');
                case 'u' -> {
                    if (pos + 4 > text.length()) {
                        throw error("Incomplete unicode escape");
                    }
                    String hex = text.substring(pos, pos + 4);
                    pos += 4;
                    try {
                        out.append((char) Integer.parseInt(hex, 16));
                    } catch (NumberFormatException ex) {
                        throw error("Invalid unicode escape");
                    }
                }
                default -> throw error("Invalid escape '\\" + escape + "'");
            }
        }
        throw error("Unterminated string");
    }

    private Object parseNumber() {
        int start = pos;
        while (pos < text.length()) {
            char c = text.charAt(pos);
            if ((c >= '0' && c <= '9') || c == '-' || c == '+'
                    || c == '.' || c == 'e' || c == 'E') {
                pos++;
            } else {
                break;
            }
        }
        String raw = text.substring(start, pos);
        try {
            if (raw.indexOf('.') >= 0 || raw.indexOf('e') >= 0
                    || raw.indexOf('E') >= 0) {
                return Double.valueOf(raw);
            }
            return Long.valueOf(raw);
        } catch (NumberFormatException ex) {
            throw error("Invalid number '" + raw + "'");
        }
    }

    private Object parseLiteral(String literal, Object value) {
        if (!text.startsWith(literal, pos)) {
            throw error("Expected '" + literal + "'");
        }
        pos += literal.length();
        return value;
    }

    private void skipWhitespace() {
        while (pos < text.length() && Character.isWhitespace(text.charAt(pos))) {
            pos++;
        }
    }

    private char peek() {
        if (pos >= text.length()) {
            throw error("Unexpected end of data");
        }
        return text.charAt(pos);
    }

    private char next() {
        char c = peek();
        pos++;
        return c;
    }

    private void expect(char expected) {
        char actual = next();
        if (actual != expected) {
            throw error("Expected '" + expected + "' but found '" + actual + "'");
        }
    }

    private IllegalArgumentException error(String message) {
        return new IllegalArgumentException(message + " at position " + pos);
    }
}
