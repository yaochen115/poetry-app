import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:hongzhuang_app/main.dart';
import 'package:hongzhuang_app/models.dart';
import 'package:hongzhuang_app/simplified_chinese.dart';
import 'package:hongzhuang_app/state.dart';
import 'package:hongzhuang_app/format.dart';

void main() {
  test('精简字词均可由真实排版后的正文长按触达', () {
    final text = File('assets/data/dict.json').readAsStringSync();
    final poems = File('assets/data/poems.json').readAsStringSync();
    final repo = Repo.fromJson(poems, text);
    expect(jsonDecode(text)['pruning']['activePoems'], repo.items.length);
    final used = <String>{};
    final candidates = <String>{};
    for (final poem in repo.items) {
      final cells = formatBody(poem.category, poem.content,
              ciBreaks: poem.ciBreaks).runes
          .where((n) => !(n >= 0x3001 && n <= 0x303f ||
              n >= 0xff00 && n <= 0xff0f || n >= 0xff1a && n <= 0xff1f ||
              [0x2018, 0x2019, 0x201c, 0x201d, 0x2026, 0x2014, 0x2013, 0x27].contains(n)))
          .map(String.fromCharCode).where((s) => !isSpace(s)).toList();
      used.addAll(cells);
      candidates.addAll(cells);
      for (var i = 1; i < cells.length; i++) {
        candidates.add(cells[i - 1] + cells[i]);
      }
    }
    expect(repo.chars.keys.every(used.contains), isTrue);
    expect(repo.words.keys.every(candidates.contains), isTrue);
  });

  test('词库按阕排版并保留正文字符', () {
    final repo = Repo.fromJson(
      File('assets/data/poems.json').readAsStringSync(),
      '{}',
    );
    final ci = repo.items.where((poem) => poem.inCategory('词'));
    String compact(String value) => value.replaceAll(RegExp(r'\s'), '');
    for (final poem in ci) {
      final paragraphs = formatBody(poem.category, poem.content,
          ciBreaks: poem.ciBreaks).split('\n');
      expect(paragraphs.length, poem.ciBreaks.length + 1, reason: poem.id);
      expect(paragraphs.every((p) => p.startsWith('　　')), isTrue,
          reason: poem.id);
      expect(compact(paragraphs.join()), compact(poem.content), reason: poem.id);
    }
    final poem = repo.poem('song-1139')!;
    final paragraphs = formatBody(poem.category, poem.content,
        ciBreaks: poem.ciBreaks).split('\n');
    expect(paragraphs, hasLength(2));
    expect(paragraphs.first, startsWith('　　明月几时有'));
    expect(paragraphs.last, startsWith('　　转朱阁'));
  });

  test('教育部辞典保留来源词头，繁简与复词查询可用', () async {
    final text = File('assets/data/dict.json').readAsStringSync();
    final raw = jsonDecode(text) as Map<String, dynamic>;
    expect(raw['source']['repository'], 'https://github.com/g0v/moedict-data');
    expect(raw['source']['records'], 161194);
    expect(raw['source']['license'], 'CC BY-ND 3.0 TW');
    expect(raw['charProvenance']['爱']['originalHeads'], contains('愛'));
    SharedPreferences.setMockInitialValues({});
    final repo = Repo.fromJson(
      '{"items":[{"id":"test","content":"爱。"}]}', text,
    );
    final state = AppState(repo, await SharedPreferences.getInstance());
    for (final head in ['爱', '于', '於']) {
      expect(state.lookup(head, '', '').meanings, isNotEmpty);
      expect(state.lookup(head, '', '').head, head);
      expect(state.lookup(head, '', '').attribution, contains('教育部'));
    }
    final compound = state.lookup('月', '明', '');
    expect(compound.isWord, isTrue);
    expect(compound.head, '明月');
    expect(compound.meanings.single, contains('明朗的月亮。'));
    expect(compound.meanings.single, contains('【原詞頭】明月'));
    expect(compound.attribution, contains('CC BY-ND 3.0 TW'));
  });

  test('源库未注音的异体字保留原文参照，不编造读音', () {
    final repo = Repo.fromJson('{"items":[]}',
        File('assets/data/dict.json').readAsStringSync());
    expect(repo.chars['仝']!.pinyin, isEmpty);
    expect(repo.chars['仝']!.meanings.join(), contains('異體字'));
    expect(repo.chars['着']!.meanings.join(), contains('【原詞頭】著'));
  });

  testWidgets('长按显示简体释义和书证，保留来源和词典原文', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final repo = Repo.fromJson(
      '{"items":[{"id":"test","title":"测试","category":"唐诗",'
      '"content":"爱。","translation":""}]}',
      File('assets/data/dict.json').readAsStringSync(),
    );
    final converter = SimplifiedChinese(SimplifiedChinese.assetPaths
        .map((path) => File(path).readAsStringSync())
        .toList());
    final state = AppState(
      repo,
      await SharedPreferences.getInstance(),
      simplifiedChinese: converter,
    );
    await tester.pumpWidget(HzApp(state: state));
    await tester.pumpAndSettle();
    await tester.longPress(find.text('爱'));
    await tester.pumpAndSettle();
    expect(find.text('字词释义'), findsOneWidget);
    expect(find.textContaining('亲慕的情绪或亲密的感情。'), findsWidgets);
    expect(find.textContaining('《礼记．礼运》'), findsWidgets);
    expect(find.textContaining('资料来源：教育部'), findsOneWidget);
    expect(find.textContaining('本页显示简体'), findsOneWidget);
    expect(find.textContaining('CC BY-ND 3.0 TW'), findsOneWidget);
    expect(repo.chars['爱']!.meanings.join(), contains('親慕的情緒'));
    expect(tester.takeException(), isNull);
    await tester.drag(find.text('字词释义'), const Offset(0, -180));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
