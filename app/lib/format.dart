/// 正文排版规则（与原型 formatBody 完全一致）。
///
/// - 唐诗：不缩进。按标点断句后，绝句（≤4 句）一句一行；律诗等（>4 句）两句一行。
/// - 词 / 元曲 / 古文：每一行开头空两格（两个全角空格 　）。
String formatBody(String category, String raw) {
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
