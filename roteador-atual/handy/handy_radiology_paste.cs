// Handy Radiology paste processor — v9 (v8 do Bruno + negrito, CRLF e maiuscula de inicio de frase)
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

internal sealed class Rule
{
    public string Kind;
    public string Source;
    public string Target;
}

internal static class Program
{
    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    [STAThread]
    private static int Main(string[] args)
    {
        IntPtr targetWindow = GetForegroundWindow();

        try
        {
            if (args == null || args.Length == 0)
                return 0;

            string text = string.Join(" ", args);
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string rulesPath = Path.Combine(baseDir, "handy_radiology_map.tsv");

            List<Rule> rules = LoadRules(rulesPath);

            // Normalize paragraph commands before the generic rule engine.
            // ASR engines may insert a dash/comma/colon between the words or
            // around the command; treat those variants as the same command.
            text = NormalizeCommandPhrases(text);

            text = ApplyRules(text, rules, "CMD", false, true);
            text = ApplyRules(text, rules, "ALIAS", false, false, true);
            text = ApplyRules(text, rules, "MAP", true, false);

            // Paragraph commands start a new sentence. Capitalize the first
            // recognized letter after them before converting markers to CRLF.
            text = CapitalizeAfterParagraphMarkers(text);
            text = Cleanup(text);

            if (string.IsNullOrWhiteSpace(text))
                return 0;

            SetClipboardRichWithRetry(text);

            if (targetWindow != IntPtr.Zero)
            {
                SetForegroundWindow(targetWindow);
                Thread.Sleep(35);
            }

            SendKeys.SendWait("^v");
            return 0;
        }
        catch
        {
            return 2;
        }
    }

    private static List<Rule> LoadRules(string path)
    {
        List<Rule> rules = new List<Rule>();
        if (!File.Exists(path))
            return rules;

        foreach (string raw in File.ReadAllLines(path, Encoding.UTF8))
        {
            if (string.IsNullOrWhiteSpace(raw) || raw.StartsWith("#"))
                continue;

            string[] parts = raw.Split(new char[] { '\t' }, 3);
            if (parts.Length != 3)
                continue;

            rules.Add(new Rule
            {
                Kind = parts[0].Trim(),
                Source = parts[1],
                Target = parts[2]
            });
        }

        return rules;
    }

    private static string ApplyRules(
        string text,
        List<Rule> allRules,
        string kind,
        bool preserveInitialCapital,
        bool consumeTrailingPunctuation)
    {
        return ApplyRules(text, allRules, kind, preserveInitialCapital, consumeTrailingPunctuation, false);
    }

    // v9: preserveSentenceCapital mantem a maiuscula quando o termo abre a
    // frase ("Fratura de Tillaux", "Arco de Shenton"), sem desfazer o ajuste
    // do v3 que forca minuscula no meio da frase ("grau").
    private static bool AtSentenceStart(string src, int index)
    {
        int i = index - 1;
        while (i >= 0 && (src[i] == ' ' || src[i] == '\t' || src[i] == '*')) i--;
        if (i < 0) return true;
        char c = src[i];
        if (c == '.' || c == '!' || c == '?' || c == '\n' || c == '\r' || c == ':') return true;
        return i >= 1 && src[i] == '_' && src[i - 1] == '_';
    }

    private static string ApplyRules(
        string text,
        List<Rule> allRules,
        string kind,
        bool preserveInitialCapital,
        bool consumeTrailingPunctuation,
        bool preserveSentenceCapital)
    {
        IEnumerable<Rule> rules = allRules
            .Where(r => string.Equals(r.Kind, kind, StringComparison.OrdinalIgnoreCase))
            .OrderByDescending(r => r.Source.Length);

        foreach (Rule rule in rules)
        {
            string pattern =
                @"(?<![\p{L}\p{N}])" +
                Regex.Escape(rule.Source) +
                @"(?![\p{L}\p{N}])";

            if (consumeTrailingPunctuation)
                pattern += @"[\.,;:]?";

            string src = text;
            MatchEvaluator evaluator = delegate(Match m)
            {
                string replacement = rule.Target;

                if (preserveSentenceCapital &&
                    replacement.Length > 0 &&
                    m.Value.Length > 0 &&
                    char.IsLower(replacement[0]) &&
                    char.IsUpper(m.Value[0]) &&
                    AtSentenceStart(src, m.Index))
                {
                    replacement =
                        char.ToUpperInvariant(replacement[0]) +
                        replacement.Substring(1);
                }

                if (preserveInitialCapital &&
                    replacement.Length > 0 &&
                    m.Value.Length > 0 &&
                    char.IsLower(replacement[0]) &&
                    char.IsUpper(m.Value[0]))
                {
                    replacement =
                        char.ToUpperInvariant(replacement[0]) +
                        replacement.Substring(1);
                }

                return replacement;
            };

            text = Regex.Replace(
                text,
                pattern,
                evaluator,
                RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        }

        return text;
    }

    private static string NormalizeCommandPhrases(string text)
    {
        // Spoken-command separators tolerated between words. ASR engines may
        // insert punctuation/dashes while recognizing command phrases.
        string sep = @"[\s,;:\.\-–—]*";
        string paragraph = @"par(?:a|á)grafo";
        string newLine = @"nova" + sep + @"linha";

        // Highest-priority compound command for Nemotron and other streaming ASR:
        //   "ponto parágrafo nova linha"
        //   "ponto final parágrafo nova linha"
        //   "ponto novo parágrafo nova linha"
        //   "ponto final novo parágrafo nova linha"
        // Always means ONE period + TWO Enters, with the next sentence capitalized.
        text = Regex.Replace(
            text,
            @"(?<![\p{L}\p{N}])ponto(?:" + sep + @"final)?" + sep + @"(?:novo" + sep + @")?" + paragraph + sep + newLine + @"(?![\p{L}\p{N}])[\s,;:\.!?\-–—]*",
            " __HANDY_PARAGRAPH_BLANK__ ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

        // "parágrafo nova linha" / "novo parágrafo nova linha" = same result:
        // ONE period + TWO Enters. Resolve as one token so the two commands cannot
        // consume or overwrite each other later in the pipeline.
        text = Regex.Replace(
            text,
            @"(?<![\p{L}\p{N}])(?:novo" + sep + @")?" + paragraph + sep + newLine + @"(?![\p{L}\p{N}])[\s,;:\.!?\-–—]*",
            " __HANDY_PARAGRAPH_BLANK__ ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

        // "ponto final novo parágrafo" and robust variants -> one paragraph marker.
        text = Regex.Replace(
            text,
            @"(?<![\p{L}\p{N}])ponto" + sep + @"final" + sep + @"novo" + sep + paragraph + @"(?![\p{L}\p{N}])[\s,;:\.!?\-–—]*",
            " __HANDY_PARAGRAPH__ ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

        text = Regex.Replace(
            text,
            @"(?<![\p{L}\p{N}])novo" + sep + paragraph + @"(?![\p{L}\p{N}])[\s,;:\.!?\-–—]*",
            " __HANDY_PARAGRAPH__ ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

        text = Regex.Replace(
            text,
            @"(?<![\p{L}\p{N}])" + paragraph + sep + @"novo(?![\p{L}\p{N}])[\s,;:\.!?\-–—]*",
            " __HANDY_PARAGRAPH__ ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

        // Short command: "parágrafo" / "paragrafo" alone.
        text = Regex.Replace(
            text,
            @"(?<![\p{L}\p{N}])" + paragraph + @"(?![\p{L}\p{N}])[ \t,;:\.!?\-–—]*",
            " __HANDY_PARAGRAPH__ ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

        return text;
    }

    private static string CapitalizeAfterParagraphMarkers(string text)
    {
        return Regex.Replace(
            text,
            @"(__HANDY_PARAGRAPH(?:_BLANK)?__)([ \t]*)(\p{Ll})",
            delegate(Match m)
            {
                string letter = m.Groups[3].Value;
                string upper = letter.Length > 0
                    ? char.ToUpperInvariant(letter[0]).ToString()
                    : letter;
                return m.Groups[1].Value + m.Groups[2].Value + upper;
            },
            RegexOptions.CultureInvariant);
    }

    private static string Cleanup(string text)
    {
        // Radiology dictation convention:
        // "parágrafo" (or "novo parágrafo") closes the current sentence with ONE period
        // and starts the next sentence on the next line. Any punctuation that the
        // ASR inserted immediately before the command is normalized to a period.
        // Compound paragraph + new-line command: close the sentence and leave
        // one blank line (period + two Enters).
        text = Regex.Replace(
            text,
            @"[ \t]*(?:[,;:.!?\-–—][ \t]*)*__HANDY_PARAGRAPH_BLANK__[ \t]*",
            ".\r\n\r\n");

        text = Regex.Replace(
            text,
            @"[ \t]*(?:[,;:.!?\-–—][ \t]*)*__HANDY_PARAGRAPH__[ \t]*",
            ".\r\n");

        // Explicit double-line command remains available separately.
        text = Regex.Replace(text, @"[ \t]*__HANDY_BLANKLINE__[ \t]*", "\r\n\r\n");

        // "nova linha" only breaks the line and does not force punctuation.
        text = Regex.Replace(text, @"[ \t]*__HANDY_NL__[ \t]*", "\r\n");

        // Remove spaces before punctuation and closing delimiters.
        text = Regex.Replace(text, @"[ \t]+([,;:.!?%\)\]\}])", "$1");

        // Remove spaces immediately after opening delimiters.
        text = Regex.Replace(text, @"([\(\[\{])[ \t]+", "$1");

        // Portuguese decimal dictation: "1 vírgula 5" -> "1,5".
        text = Regex.Replace(text, @"(?<=\d),[ \t]+(?=\d)", ",");
        text = Regex.Replace(text, @"(?<=\d)\.[ \t]+(?=\d)", ".");

        // Tidy line boundaries without destroying intentional blank lines.
        text = Regex.Replace(text, @"[ \t]+\r?\n", "\r\n");
        text = Regex.Replace(text, @"\r?\n[ \t]+", "\r\n");
        text = Regex.Replace(text, @"(\r\n){3,}", "\r\n\r\n");

        return text.Trim();
    }

    // ------------------------------------------------------------------
    // v9 — NEGRITO
    // O roteador marca os cabecalhos como **TECNICA:**. Aqui as marcas viram
    // negrito de verdade em HTML (editores web, Word) e RTF (RichEdit, a maioria
    // dos RIS de desktop). O texto puro do clipboard sai SEM as marcas, entao
    // um campo de texto simples recebe o laudo limpo.
    // ------------------------------------------------------------------
    internal static string ToCrlf(string s)
    {
        return Regex.Replace(s, @"\r?\n", "\r\n");
    }

    internal static string StripMarks(string s)
    {
        return s.Replace("**", "");
    }

    private static string HtmlEscape(string s)
    {
        return s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;");
    }

    internal static string ToHtmlFragment(string text)
    {
        string[] lines = Regex.Split(text, @"\r?\n");
        StringBuilder sb = new StringBuilder();
        bool bold = false;
        foreach (string line in lines)
        {
            StringBuilder p = new StringBuilder();
            string[] parts = line.Split(new string[] { "**" }, StringSplitOptions.None);
            for (int i = 0; i < parts.Length; i++)
            {
                if (i > 0) { bold = !bold; p.Append(bold ? "<b>" : "</b>"); }
                p.Append(HtmlEscape(parts[i]));
            }
            if (bold) { p.Append("</b>"); bold = false; }
            string body = p.ToString();
            if (body.Trim().Length == 0) body = "&nbsp;";
            sb.Append("<p style=\"margin:0\">").Append(body).Append("</p>");
        }
        return sb.ToString();
    }

    internal static string ToCfHtml(string fragment)
    {
        const string header =
            "Version:0.9\r\nStartHTML:{0:D10}\r\nEndHTML:{1:D10}\r\n" +
            "StartFragment:{2:D10}\r\nEndFragment:{3:D10}\r\n";
        string pre = "<html><body>\r\n<!--StartFragment-->";
        string post = "<!--EndFragment-->\r\n</body></html>";
        int hdr = Encoding.UTF8.GetByteCount(string.Format(header, 0, 0, 0, 0));
        int startFrag = hdr + Encoding.UTF8.GetByteCount(pre);
        int endFrag = startFrag + Encoding.UTF8.GetByteCount(fragment);
        int endHtml = endFrag + Encoding.UTF8.GetByteCount(post);
        return string.Format(header, hdr, endHtml, startFrag, endFrag) + pre + fragment + post;
    }

    internal static string ToRtf(string text)
    {
        StringBuilder sb = new StringBuilder();
        sb.Append(@"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fswiss\fcharset0 Arial;}}\f0\fs22 ");
        string[] lines = Regex.Split(text, @"\r?\n");
        bool bold = false;
        for (int li = 0; li < lines.Length; li++)
        {
            if (li > 0) sb.Append(@"\par ");
            string[] parts = lines[li].Split(new string[] { "**" }, StringSplitOptions.None);
            for (int i = 0; i < parts.Length; i++)
            {
                if (i > 0) { bold = !bold; sb.Append(bold ? @"\b " : @"\b0 "); }
                foreach (char c in parts[i])
                {
                    if (c == '\\' || c == '{' || c == '}') sb.Append('\\').Append(c);
                    else if (c < 128) sb.Append(c);
                    else sb.Append(@"\u").Append(((int)c).ToString()).Append('?');
                }
            }
            if (bold) { sb.Append(@"\b0 "); bold = false; }
        }
        sb.Append('}');
        return sb.ToString();
    }

    private static void SetClipboardRichWithRetry(string text)
    {
        string plain = ToCrlf(StripMarks(text));
        if (text.IndexOf("**", StringComparison.Ordinal) < 0)
        {
            SetClipboardWithRetry(plain);
            return;
        }
        DataObject d = new DataObject();
        d.SetData(DataFormats.UnicodeText, plain);
        d.SetData(DataFormats.Text, plain);
        d.SetData("HTML Format", new MemoryStream(Encoding.UTF8.GetBytes(ToCfHtml(ToHtmlFragment(text)))));
        d.SetData(DataFormats.Rtf, ToRtf(text));

        Exception last = null;
        for (int i = 0; i < 8; i++)
        {
            try
            {
                Clipboard.SetDataObject(d, true);
                return;
            }
            catch (Exception ex)
            {
                last = ex;
                Thread.Sleep(25);
            }
        }
        if (last != null)
            throw last;
    }

    private static void SetClipboardWithRetry(string text)
    {
        Exception last = null;

        for (int i = 0; i < 8; i++)
        {
            try
            {
                Clipboard.SetText(text);
                return;
            }
            catch (Exception ex)
            {
                last = ex;
                Thread.Sleep(25);
            }
        }

        if (last != null)
            throw last;
    }
}
