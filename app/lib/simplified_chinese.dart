import 'dart:math' as math;

/// OpenCC 字形表。先归一台湾字形，再转为简体，每次优先匹配最长词组。
class SimplifiedChinese {
  static const assetPaths = [
    'assets/opencc/TWVariantsRevPhrases.txt',
    'assets/opencc/TWVariantsRev.txt',
    'assets/opencc/TSPhrases.txt',
    'assets/opencc/TSCharacters.txt',
  ];

  final _ConversionTable _taiwan;
  final _ConversionTable _simplified;

  SimplifiedChinese(List<String> tables)
      : _taiwan = _ConversionTable(tables.take(2)),
        _simplified = _ConversionTable(tables.skip(2));

  String convert(String value) => _simplified.apply(_taiwan.apply(value));
}

class _ConversionTable {
  final Map<String, String> _entries = {};
  int _maxLength = 1;

  _ConversionTable(Iterable<String> tables) {
    for (final table in tables) {
      for (final line in table.split('\n')) {
        final parts = line.trim().split('\t');
        if (parts.length != 2) continue;
        final key = parts.first;
        // OpenCC puts its preferred conversion first when a key has alternatives.
        _entries.putIfAbsent(key, () => parts.last.split(' ').first);
        _maxLength = math.max(_maxLength, key.length);
      }
    }
  }

  String apply(String input) {
    final output = StringBuffer();
    var start = 0;
    while (start < input.length) {
      var end = math.min(start + _maxLength, input.length);
      String? replacement;
      while (end > start) {
        replacement = _entries[input.substring(start, end)];
        if (replacement != null) break;
        end--;
      }
      if (replacement == null) {
        output.writeCharCode(input.codeUnitAt(start++));
      } else {
        output.write(replacement);
        start = end;
      }
    }
    return output.toString();
  }
}
