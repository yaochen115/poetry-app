import 'dart:convert';

/// 单条注释（重点注释，界面不展示，仅供数据完整性保留）。
class Note {
  final String term;
  final String meaning;
  const Note({required this.term, required this.meaning});

  static Note fromJson(Map<String, dynamic> j) => Note(
        term: (j['term'] ?? '').toString(),
        meaning: (j['meaning'] ?? '').toString(),
      );
}

/// 一首诗词。
class Poem {
  final String id;
  final String category; // 唐诗 / 宋词 / 元曲 / 古文
  final List<String> tags;
  final String title;
  final String subtitle;
  final String author;
  final String dynasty;
  final String? excerptOf;
  final String excerptNote;
  final String content;
  final String translation;
  final List<Note> notes;

  const Poem({
    required this.id,
    required this.category,
    required this.tags,
    required this.title,
    required this.subtitle,
    required this.author,
    required this.dynasty,
    required this.excerptOf,
    required this.excerptNote,
    required this.content,
    required this.translation,
    required this.notes,
  });

  bool get isTang => category == '唐诗' || category == '诗';

  /// 兼容旧存储槽位；新增历代诗词显示实际体裁，不把宋诗标成唐诗。
  bool inCategory(String key) {
    const groups = {'唐诗': '诗', '宋词': '词', '元曲': '曲', '古文': '文'};
    return (groups[category] ?? category) == (groups[key] ?? key);
  }

  static Poem fromJson(Map<String, dynamic> j) => Poem(
        id: (j['id'] ?? '').toString(),
        category: (j['genre'] ?? j['category'] ?? '').toString(),
        tags: ((j['tags'] ?? []) as List).map((e) => e.toString()).toList(),
        title: (j['title'] ?? '').toString(),
        subtitle: (j['subtitle'] ?? '').toString(),
        author: (j['author'] ?? '').toString(),
        dynasty: (j['dynasty'] ?? '').toString(),
        excerptOf: j['excerptOf'] as String?,
        excerptNote: (j['excerptNote'] ?? '').toString(),
        content: (j['content'] ?? '').toString(),
        translation: (j['translation'] ?? '').toString(),
        notes: ((j['notes'] ?? []) as List)
            .map((e) => Note.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
      );
}

/// 单字词典条目。
class DictEntry {
  final List<String> pinyin;
  final List<String> meanings; // 现代义
  final List<String> ancient; // 古汉语义

  const DictEntry({
    required this.pinyin,
    required this.meanings,
    required this.ancient,
  });

  static DictEntry fromJson(Map<String, dynamic> j) => DictEntry(
        pinyin: ((j['pinyin'] ?? []) as List).map((e) => e.toString()).toList(),
        meanings:
            ((j['meanings'] ?? []) as List).map((e) => e.toString()).toList(),
        ancient:
            ((j['ancient'] ?? []) as List).map((e) => e.toString()).toList(),
      );
}

/// 诗词库（只读内置数据）。
class Repo {
  final Map<String, Poem> byId;
  final List<Poem> items; // 按诗/词/曲/文顺序
  final Map<String, DictEntry> chars;
  final Map<String, String> words; // 双字词 -> 释义

  const Repo({
    required this.byId,
    required this.items,
    required this.chars,
    required this.words,
  });

  Poem? poem(String id) => byId[id];

  static Repo fromJson(String poemsJson, String dictJson) {
    final poems = jsonDecode(poemsJson) as Map<String, dynamic>;
    final dict = jsonDecode(dictJson) as Map<String, dynamic>;
    final disabledIds = ((poems['disabledEntries'] ?? []) as List)
        .map((e) => (e as Map<String, dynamic>)['id'].toString())
        .toSet();
    final selection = poems['selectionProfile'] as Map<String, dynamic>?;
    final selectedIds = selection == null
        ? null
        : (selection['ids'] as List).map((id) => id.toString()).toSet();

    final imports = poems['translationImports'] as Map<String, dynamic>? ?? {};
    final items = ((poems['items'] ?? []) as List)
        .map((e) {
          final row = Map<String, dynamic>.from(e as Map);
          final extra = imports[row['id']];
          // Partial imports provide readable translations while the canonical
          // entry retains its pending enrichment status. Existing text wins.
          if ((row['translation'] ?? '').toString().trim().isEmpty &&
              extra is Map && extra['baseContent'] == row['content'] &&
              extra['baseAuthor'] == row['author'] &&
              extra['translation'] is String &&
              (extra['translation'] as String).trim().isNotEmpty) {
            row['translation'] = extra['translation'];
            for (final field in ['notes', 'tags']) {
              if ((row[field] as List? ?? []).isEmpty && extra[field] is List) {
                row[field] = extra[field];
              }
            }
          }
          return Poem.fromJson(row);
        })
        .where((p) => !disabledIds.contains(p.id) &&
            (selectedIds == null || selectedIds.contains(p.id)))
        .toList();
    final byId = {for (final p in items) p.id: p};

    final charsRaw = (dict['chars'] ?? {}) as Map<String, dynamic>;
    final chars = <String, DictEntry>{};
    charsRaw.forEach((k, v) {
      chars[k] = DictEntry.fromJson(Map<String, dynamic>.from(v as Map));
    });

    final wordsRaw = (dict['words'] ?? {}) as Map<String, dynamic>;
    final words = <String, String>{};
    wordsRaw.forEach((k, v) {
      words[k] = v.toString();
    });

    return Repo(byId: byId, items: items, chars: chars, words: words);
  }
}
