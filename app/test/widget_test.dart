import 'dart:io';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';

import 'package:hongzhuang_app/models.dart';

void main() {
  test('当前启用原文；译注完整条目有标签、注释及字典覆盖', () {
    final poemsJson =
        File('assets/data/poems.json').readAsStringSync();
    final dictJson = File('assets/data/dict.json').readAsStringSync();
    final repo = Repo.fromJson(poemsJson, dictJson);
    final dictRaw = jsonDecode(dictJson) as Map<String, dynamic>;
    final raw = jsonDecode(poemsJson) as Map<String, dynamic>;
    final rawById = {for (final p in raw['items'] as List) p['id']: p};

    final profile = raw['selectionProfile'] as Map<String, dynamic>;
    expect(repo.items.length, (profile['ids'] as List).length);
    if (profile['scope'] == 'all_valid_stored') {
      final disabled = (raw['disabledEntries'] as List)
          .map((row) => row['id'])
          .toSet();
      final expected = (raw['items'] as List)
          .map((row) => row['id'])
          .where((id) => !disabled.contains(id))
          .toSet();
      expect(repo.byId.keys.toSet(), expected);
    }
    // 允许负责人批准的清空状态；重建后每个条目仍须具备有效内容。
    for (final item in repo.chars.entries) {
      final entry = item.value;
      // 教育部部分异体字仅注明参照字，原库没有注音，不能编造读音。
      if (entry.pinyin.isEmpty) {
        expect(dictRaw['source']['datasetId'], 'moe-revised');
        expect(dictRaw['charProvenance'][item.key]['missingSourceReading'], isTrue);
      }
      expect([...entry.meanings, ...entry.ancient], isNotEmpty);
    }
    for (final meaning in repo.words.values) {
      expect(meaning.trim(), isNotEmpty);
    }
    if (raw.containsKey('enrichmentReset')) {
      for (final row in raw['items'] as List) {
        expect(row['translation'], isEmpty, reason: row['id']);
        expect(row['notes'], isEmpty, reason: row['id']);
        expect(row['editorialStatus'], 'original_only', reason: row['id']);
      }
    }

    // D阶段待补原文留空译注，完整篇目保留有效译注。
    for (final p in repo.items) {
      expect(p.content, isNotEmpty, reason: p.id);
      if (p.translation.isEmpty) {
        expect(p.notes, isEmpty, reason: p.id);
      } else if (rawById[p.id]['editorialStatus'] != 'original_only') {
        expect(p.notes.length, greaterThanOrEqualTo(3), reason: p.id);
        expect(p.notes.length, lessThanOrEqualTo(18), reason: p.id);
        expect(p.tags, isNotEmpty, reason: p.id);
        for (final code in p.content.runes) {
          if ((code >= 0x4e00 && code <= 0x9fff) || code == 0x3007) {
            final char = String.fromCharCode(code);
            final entry = repo.chars[char];
            expect(entry, isNotNull, reason: '${p.id}: $char');
            expect(entry!.pinyin, isNotEmpty, reason: '${p.id}: $char');
            expect([...entry.meanings, ...entry.ancient], isNotEmpty,
                reason: '${p.id}: $char');
          }
        }
      }
    }

    final counts = profile['expectedCounts'] as Map<String, dynamic>;
    for (final cat in counts.keys) {
      expect(
        repo.items.where((p) => rawById[p.id]['category'] == cat).length,
        counts[cat],
      );
    }
    final classics = repo.items
        .where((p) => rawById[p.id]['category'] == '经典').toList();
    expect(classics, hasLength(600));
    expect(classics.every((p) => p.inCategory('唐诗') && p.inCategory('诗')), isTrue);
    final liSao = classics.singleWhere((p) => p.title == '离骚');
    expect(liSao.author, '屈原');
    expect(liSao.content, startsWith('帝高阳之苗裔兮'));
    expect(liSao.content, endsWith('吾将从彭咸之所居！'));
    expect(
      classics.where((p) => p.title.startsWith('古诗十九首·')),
      hasLength(19),
    );
    final maxYuanChars = profile['maxYuanHanChars'] as int?;
    if (maxYuanChars != null) {
      for (final poem in repo.items.where((p) => p.category == '元曲')) {
        final chars = poem.content.runes.where((c) =>
            (c >= 0x3400 && c <= 0x9fff) || c == 0x3007).length;
        expect(chars, lessThanOrEqualTo(maxYuanChars), reason: poem.id);
      }
    }
  });

  test('历代诗按实际体裁展示，同时兼容旧分类入口和原学习ID', () {
    final json = jsonEncode({'items': [{
      'id': 'tang-1051', 'category': '唐诗', 'genre': '诗',
      'title': '小池', 'author': '杨万里', 'dynasty': '宋', 'content': '泉眼无声惜细流。'
    }]});
    final p = Repo.fromJson(json, '{"chars":{},"words":{}}').items.single;
    expect(p.id, 'tang-1051');
    expect(p.category, '诗');
    expect(p.dynasty, '宋');
    expect(p.inCategory('唐诗'), isTrue);
    expect(p.inCategory('宋词'), isFalse);
    expect(p.isTang, isTrue);
  });

  test('部分译文可读取，原有译文优先，原文变更拒绝旧补充记录', () {
    final row = {'id':'tang-001','content':'原文','author':'作者','translation':''};
    final extra = {'baseContent':'原文','baseAuthor':'作者','translation':'已采集的译文','notes':[],'tags':[]};
    const dictionaryJson = '{"chars":{},"words":{}}';
    String encode() => jsonEncode({'items':[row],'translationImports':{'tang-001':extra}});
    expect(Repo.fromJson(encode(), dictionaryJson).items.single.translation, '已采集的译文');
    row['translation'] = '原有译文';
    expect(Repo.fromJson(encode(), dictionaryJson).items.single.translation, '原有译文');
    row['translation'] = '';
    extra['baseContent'] = '其他原文';
    expect(Repo.fromJson(encode(), dictionaryJson).items.single.translation, isEmpty);
  });
}
