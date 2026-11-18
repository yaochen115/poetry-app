/// 正文排版规则。
///
/// - 唐诗：不缩进。按标点断句后，绝句（≤4 句）一句一行；律诗等（>4 句）两句一行。
/// - 词：按分阕位置合并句行，每阕开头空两格。
/// - 元曲 / 古文：每一行开头空两格。
String formatBody(String category, String raw, {List<int> ciBreaks = const []}) {
  if (category == '宋词' || category == '词') {
    final paragraphs = <String>[];
    var start = 0;
    for (final end in [...ciBreaks, raw.length]) {
      if (end <= start || end > raw.length) continue;
      final paragraph = raw.substring(start, end)
          .replaceAll(RegExp(r'\s*[\r\n]+\s*'), '')
          .trim();
      if (paragraph.isNotEmpty) paragraphs.add('　　$paragraph');
      start = end;
    }
    return paragraphs.join('\n');
  }

  final lines = raw.split('\n');
  if (category == '唐诗' || category == '诗') {
    final all = <String>[];
    for (final line in lines) {
      final s = line.trim();
      if (s.isEmpty) continue;
      var cur = '';
      for (final ch in s.split('')) {
        cur += ch;
        if (ch == '，' ||
            ch == '。' ||
            ch == '？' ||
            ch == '！' ||
            ch == '?' ||
            ch == '!') {
          all.add(cur);
          cur = '';
        }
      }
      if (cur.trim().isNotEmpty) all.add(cur);
    }
    if (all.length <= 4) return all.join('\n');
    final out = <String>[];
    for (var i = 0; i < all.length; i += 2) {
      out.add(all[i] + (i + 1 < all.length ? all[i + 1] : ''));
    }
    return out.join('\n');
  }

  final out = <String>[];
  for (final line in lines) {
    final s = line.replaceFirst(RegExp(r'^\s+'), '');
    out.add(s.isEmpty ? '' : '　　$s');
  }
  return out.join('\n');
}

/// 是否为不可查询的空白字符（空格、换行、全角空格等）。
bool isSpace(String ch) {
  if (ch.isEmpty) return true;
  if (ch == '\n' || ch == '\r' || ch == '\t') return true;
  return ch.trim().isEmpty;
}
