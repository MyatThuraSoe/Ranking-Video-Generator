package lrbar.license;

import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JSpinner;
import javax.swing.JTable;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.UIManager;
import javax.swing.border.Border;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableCellRenderer;
import javax.swing.table.JTableHeader;
import java.awt.Color;
import java.awt.Component;
import java.awt.Cursor;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;

/** Light palette and small component factories shared by the whole window. */
public final class Theme {

    public static final Color BG = new Color(0xf4f6fa);
    public static final Color SURFACE = new Color(0xffffff);
    public static final Color SURFACE2 = new Color(0xf6f8fc);
    public static final Color SURFACE3 = new Color(0xeaf0f8);
    public static final Color BORDER = new Color(0xdde4ee);
    public static final Color BORDER_INPUT = new Color(0xc7d2e2);
    public static final Color TEXT = new Color(0x111827);
    public static final Color TEXT_SOFT = new Color(0x334155);
    public static final Color DIM = new Color(0x64748b);
    public static final Color ACCENT = new Color(0x2563eb);
    public static final Color ACCENT_HOVER = new Color(0x1d4ed8);
    public static final Color PRIMARY = new Color(0x1f2937);
    public static final Color PRIMARY_HOVER = new Color(0x111827);
    public static final Color PRIMARY_PRESSED = new Color(0x0b1220);
    public static final Color PRIMARY_BORDER = new Color(0x0f172a);
    public static final Color OK = new Color(0x15803d);
    public static final Color WARN = new Color(0xb45309);
    public static final Color ERR = new Color(0xb91c1c);
    public static final Color DANGER = new Color(0xc02626);
    public static final Color SELECTION = new Color(0xcfe0ff);
    public static final Color SELECTED_TEXT = new Color(0x0f172a);

    public static final Font UI = new Font("Segoe UI", Font.PLAIN, 13);
    public static final Font BOLD = new Font("Segoe UI", Font.BOLD, 13);
    public static final Font TITLE = new Font("Segoe UI", Font.BOLD, 22);
    public static final Font SUBTITLE = new Font("Segoe UI", Font.PLAIN, 12);
    public static final Font MONO = new Font("Consolas", Font.PLAIN, 12);
    public static final Font MONO_SMALL = new Font("Consolas", Font.PLAIN, 11);

    private Theme() {
    }

    public static void install() {
        try {
            UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
        } catch (Exception ignored) {
            // keep the default look and feel
        }
        UIManager.put("Panel.background", BG);
        UIManager.put("Label.foreground", TEXT);
        UIManager.put("Label.font", UI);
        UIManager.put("TextField.background", SURFACE2);
        UIManager.put("TextField.foreground", TEXT);
        UIManager.put("TextField.caretForeground", TEXT);
        UIManager.put("TextField.selectionBackground", SELECTION);
        UIManager.put("TextField.selectionForeground", SELECTED_TEXT);
        UIManager.put("TextArea.background", SURFACE2);
        UIManager.put("TextArea.foreground", TEXT);
        UIManager.put("TextArea.caretForeground", TEXT);
        UIManager.put("TextArea.selectionBackground", SELECTION);
        UIManager.put("TextArea.selectionForeground", SELECTED_TEXT);
        UIManager.put("Button.background", SURFACE2);
        UIManager.put("Button.foreground", TEXT);
        UIManager.put("Button.font", BOLD);
        UIManager.put("TabbedPane.background", BG);
        UIManager.put("TabbedPane.foreground", TEXT_SOFT);
        UIManager.put("TabbedPane.selected", SURFACE);
        UIManager.put("TabbedPane.contentAreaColor", BG);
        UIManager.put("Table.background", SURFACE);
        UIManager.put("Table.foreground", TEXT_SOFT);
        UIManager.put("Table.selectionBackground", SELECTION);
        UIManager.put("Table.selectionForeground", SELECTED_TEXT);
        UIManager.put("Table.gridColor", BORDER);
        UIManager.put("TableHeader.background", SURFACE3);
        UIManager.put("TableHeader.foreground", TEXT);
        UIManager.put("TableHeader.font", BOLD);
        UIManager.put("ScrollPane.background", BG);
        UIManager.put("Viewport.background", SURFACE);
        UIManager.put("CheckBox.background", BG);
        UIManager.put("CheckBox.foreground", TEXT_SOFT);
        UIManager.put("RadioButton.background", BG);
        UIManager.put("RadioButton.foreground", TEXT_SOFT);
        UIManager.put("RadioButton.font", UI);
        UIManager.put("OptionPane.background", SURFACE);
        UIManager.put("OptionPane.messageForeground", TEXT);
        UIManager.put("ComboBox.background", SURFACE2);
        UIManager.put("ComboBox.foreground", TEXT);
        UIManager.put("Spinner.background", SURFACE2);
        UIManager.put("Spinner.foreground", TEXT);
        UIManager.put("ToolTip.background", SURFACE3);
        UIManager.put("ToolTip.foreground", TEXT);
    }

    public static Border inputBorder() {
        return BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(BORDER_INPUT),
                new EmptyBorder(4, 8, 4, 8));
    }

    public static Border cardBorder() {
        return BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(BORDER),
                new EmptyBorder(14, 16, 14, 16));
    }

    public static JPanel card() {
        JPanel panel = new JPanel();
        panel.setBackground(SURFACE);
        panel.setBorder(cardBorder());
        return panel;
    }

    public static JLabel title(String text) {
        JLabel label = new JLabel(text);
        label.setFont(TITLE);
        label.setForeground(TEXT);
        return label;
    }

    public static JLabel subtitle(String text) {
        JLabel label = new JLabel(text);
        label.setFont(SUBTITLE);
        label.setForeground(DIM);
        return label;
    }

    public static JLabel label(String text) {
        JLabel label = new JLabel(text);
        label.setFont(UI);
        label.setForeground(TEXT_SOFT);
        return label;
    }

    public static JLabel fieldLabel(String text) {
        JLabel label = new JLabel(text);
        label.setFont(BOLD);
        label.setForeground(DIM);
        return label;
    }

    public static JLabel hint(String text) {
        JLabel label = new JLabel(text);
        label.setFont(SUBTITLE);
        label.setForeground(DIM);
        return label;
    }

    public static JTextField textField() {
        JTextField field = new JTextField();
        field.setFont(UI);
        field.setBackground(SURFACE2);
        field.setForeground(TEXT);
        field.setCaretColor(TEXT);
        field.setSelectionColor(SELECTION);
        field.setSelectedTextColor(SELECTED_TEXT);
        field.setBorder(inputBorder());
        return field;
    }

    public static JTextField monoField() {
        JTextField field = textField();
        field.setFont(new Font("Consolas", Font.PLAIN, 14));
        return field;
    }

    public static JTextArea textArea() {
        JTextArea area = new JTextArea();
        area.setFont(UI);
        area.setBackground(SURFACE2);
        area.setForeground(TEXT);
        area.setCaretColor(TEXT);
        area.setSelectionColor(SELECTION);
        area.setSelectedTextColor(SELECTED_TEXT);
        area.setBorder(new EmptyBorder(6, 8, 6, 8));
        area.setLineWrap(true);
        area.setWrapStyleWord(true);
        return area;
    }

    public static JTextArea monoArea() {
        JTextArea area = textArea();
        area.setFont(MONO_SMALL);
        return area;
    }

    public static JButton button(String text) {
        JButton button = new JButton(text);
        button.setFont(BOLD);
        button.setForeground(TEXT_SOFT);
        button.setBackground(SURFACE2);
        button.setOpaque(true);
        button.setFocusPainted(false);
        button.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        button.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(BORDER_INPUT),
                new EmptyBorder(7, 14, 7, 14)));
        return button;
    }

    public static JButton primaryButton(String text) {
        // The Windows look-and-feel ignores setBackground on JButtons, so the
        // dark fill is painted explicitly. Rounded corners stay transparent.
        JButton button = new JButton(text) {
            @Override
            protected void paintComponent(Graphics g) {
                Graphics2D g2 = (Graphics2D) g.create();
                g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING,
                        RenderingHints.VALUE_ANTIALIAS_ON);
                Color fill = PRIMARY;
                if (getModel().isPressed()) {
                    fill = PRIMARY_PRESSED;
                } else if (getModel().isRollover()) {
                    fill = PRIMARY_HOVER;
                }
                g2.setColor(fill);
                g2.fillRoundRect(0, 0, getWidth() - 1, getHeight() - 1, 10, 10);
                g2.setColor(PRIMARY_BORDER);
                g2.drawRoundRect(0, 0, getWidth() - 1, getHeight() - 1, 10, 10);
                g2.dispose();
                super.paintComponent(g);
            }

            @Override
            public boolean isOpaque() {
                return false;
            }
        };
        button.setFont(BOLD);
        button.setForeground(Color.WHITE);
        button.setContentAreaFilled(false);
        button.setOpaque(false);
        button.setFocusPainted(false);
        button.setRolloverEnabled(true);
        button.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        button.setBorder(new EmptyBorder(9, 16, 9, 16));
        return button;
    }

    public static JButton dangerButton(String text) {
        JButton button = button(text);
        button.setForeground(ERR);
        return button;
    }

    public static JScrollPane scroll(Component content) {
        JScrollPane pane = new JScrollPane(content);
        pane.setBorder(BorderFactory.createLineBorder(BORDER_INPUT));
        pane.getViewport().setBackground(SURFACE);
        pane.setBackground(BG);
        pane.getVerticalScrollBar().setUnitIncrement(16);
        return pane;
    }

    public static void styleTable(JTable table) {
        table.setFont(UI);
        table.setBackground(SURFACE);
        table.setForeground(TEXT_SOFT);
        table.setSelectionBackground(SELECTION);
        table.setSelectionForeground(SELECTED_TEXT);
        table.setGridColor(BORDER);
        table.setRowHeight(28);
        table.setShowVerticalLines(false);
        table.setFillsViewportHeight(true);
        table.setAutoCreateRowSorter(true);
        JTableHeader header = table.getTableHeader();
        header.setBackground(SURFACE3);
        header.setForeground(TEXT);
        header.setFont(BOLD);
        header.setReorderingAllowed(false);
        DefaultTableCellRenderer renderer = new DefaultTableCellRenderer();
        renderer.setBackground(SURFACE);
        renderer.setForeground(TEXT_SOFT);
        renderer.setBorder(new EmptyBorder(0, 8, 0, 8));
        table.setDefaultRenderer(Object.class, renderer);
    }

    public static void setStatus(JLabel label, String text, boolean error) {
        label.setText(text == null ? "" : text);
        label.setForeground(error ? ERR : OK);
        label.setVisible(text != null && !text.isBlank());
    }

    public static void setNeutralStatus(JLabel label, String text) {
        label.setText(text == null ? "" : text);
        label.setForeground(DIM);
        label.setVisible(text != null && !text.isBlank());
    }

    public static void styleSpinner(JSpinner spinner) {
        spinner.setBackground(SURFACE2);
        spinner.setForeground(TEXT);
        spinner.setBorder(BorderFactory.createLineBorder(BORDER_INPUT));
        if (spinner.getEditor() instanceof JSpinner.DefaultEditor) {
            JTextField field = ((JSpinner.DefaultEditor) spinner.getEditor()).getTextField();
            field.setBackground(SURFACE2);
            field.setForeground(TEXT);
            field.setCaretColor(TEXT);
            field.setSelectionColor(SELECTION);
            field.setSelectedTextColor(SELECTED_TEXT);
            field.setBorder(new EmptyBorder(4, 6, 4, 4));
            field.setFont(UI);
        }
    }
}
