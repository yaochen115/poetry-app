import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:hongzhuang_app/models.dart';
import 'package:hongzhuang_app/state.dart';

Repo sampleRepo() => Repo.fromJson(jsonEncode({
  'items': [
    for (final category in ['唐诗', '宋词', '元曲', '古文']) ...[
      {'id': '$category-ready', 'category': category, 'content': '正文。', 'translation': '完整译文。'},
      {'id': '$category-empty', 'category': category, 'content': '正文。', 'translation': ''},
      {'id': '$category-space', 'category': category, 'content': '正文。', 'translation': '  \n '},
    ],
  ],
}), '{"chars":{},"words":{}}');

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('四类未习随机优先有译文，仍保留全部未习候选', () async {
    SharedPreferences.setMockInitialValues({});
    final state = AppState(sampleRepo(), await SharedPreferences.getInstance());
    for (final category in ['唐诗', '宋词', '元曲', '古文']) {
      expect(state.poolOf(category).length, 3);
      for (var i = 0; i < 30; i++) {
        expect(state.randomFromCategory(category), '$category-ready');
      }
    }
    state.pageController.dispose();
    state.dispose();
  });

  test('有译文篇目已学后回退到本类别无译文未习，空池返回空', () async {
    SharedPreferences.setMockInitialValues({});
    final state = AppState(sampleRepo(), await SharedPreferences.getInstance());
    state.setMastery('唐诗-ready', 1);
    for (var i = 0; i < 30; i++) {
      expect(['唐诗-empty', '唐诗-space'], contains(state.randomFromCategory('唐诗')));
    }
    state.setMastery('唐诗-empty', 2);
    state.setMastery('唐诗-space', 1);
    expect(state.randomFromCategory('唐诗'), isNull);
    expect(state.randomFromCategory('不存在的分类'), isNull);
    state.pageController.dispose();
    state.dispose();
  });

  test('日省随机在选定掌握度内优先译文，并支持无译文回退', () async {
    SharedPreferences.setMockInitialValues({});
    final state = AppState(sampleRepo(), await SharedPreferences.getInstance());
    state.setMastery('宋词-ready', 1);
    state.setMastery('宋词-empty', 1);
    state.setMastery('元曲-ready', 2);
    for (var i = 0; i < 30; i++) {
      expect(state.randomFromMastery(1), '宋词-ready');
    }
    state.setMastery('宋词-ready', 2);
    expect(state.randomFromMastery(1), '宋词-empty');
    expect(state.randomFromMastery(3), isNull);
    state.pageController.dispose();
    state.dispose();
  });

  test('正式译文补充表通过应用入口可读取', () {
    final poems = File('assets/data/poems.json').readAsStringSync();
    final raw = jsonDecode(poems) as Map<String, dynamic>;
    final repo = Repo.fromJson(poems, File('assets/data/dict.json').readAsStringSync());
    final imports = raw['translationImports'] as Map<String, dynamic>;
    final expected = imports.keys.where(repo.byId.containsKey).toSet();
    expect(expected, isNotEmpty);
    expect(repo.items.where((p) => p.translation.trim().isNotEmpty).map((p) => p.id).toSet(), expected);
    for (final id in expected) {
      expect(repo.poem(id)!.translation, imports[id]['translation']);
      expect(imports[id]['literaryApproved'], isFalse);
      expect(imports[id]['userApprovedImport'], isTrue);
    }
  });
}
