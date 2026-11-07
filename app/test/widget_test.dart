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
    final raw = jsonDecode(poemsJson) as Map<String, dynamic>;
    final rawById = {for (final p in raw['items'] as List) p['id']: p};

    final profile = raw['selectionProfile'] as Map<String, dynamic>;
    expect(repo.items.length, (profile['ids'] as List).length);
    // 内容持续补全，不能把历史字词数量写死成上限。
    expect(repo.chars.length, greaterThanOrEqualTo(2698));
    expect(repo.words.length, greaterThanOrEqualTo(1342));

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
      expect(repo.items.where((p) => p.inCategory(cat)).length, counts[cat]);
    }
    for (final poem in repo.items.where((p) => p.category == '元曲')) {
      final chars = poem.content.runes.where((c) =>
          (c >= 0x3400 && c <= 0x9fff) || c == 0x3007).length;
      expect(chars, lessThan(100), reason: poem.id);
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
