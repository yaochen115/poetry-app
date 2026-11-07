import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hongzhuang_app/models.dart';
import 'package:hongzhuang_app/state.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final poemsJson = File('assets/data/poems.json').readAsStringSync();
  final dictJson = File('assets/data/dict.json').readAsStringSync();
  final raw = jsonDecode(poemsJson) as Map<String, dynamic>;
  final repo = Repo.fromJson(poemsJson, dictJson);

  test('保留停用原文与ID，替补可用，正常库无私用区字形', () {
    expect((raw['items'] as List).length, greaterThanOrEqualTo(4206));
    expect((raw['disabledEntries'] as List).length, 6);
    expect(repo.items.length, ((raw['selectionProfile'] as Map)['ids'] as List).length);
    final storedIds = (raw['items'] as List).map((p) => p['id']).toSet();
    for (final entry in raw['disabledEntries'] as List) {
      expect(storedIds, contains(entry['id']));
      expect(repo.poem(entry['id'] as String), isNull);
      expect(storedIds, contains(entry['replacementId']));
    }
    for (final p in repo.items) {
      expect(p.content.runes.any((c) => c >= 0xe000 && c <= 0xf8ff), isFalse,
          reason: p.id);
    }
  });

  test('未入选篇目的学习记录保留，但不进入精选收藏或当前阅读', () async {
    final selected = repo.items.map((p) => p.id).toSet();
    final archived = (raw['items'] as List)
        .firstWhere((p) => !selected.contains(p['id']) &&
            !(raw['disabledEntries'] as List).any((d) => d['id'] == p['id']))['id'] as String;
    final active = repo.items.first.id;
    SharedPreferences.setMockInitialValues({
      'current_poem_id': archived,
      'favs': [archived, active],
      'mastery_map': jsonEncode({archived: 2, active: 1}),
    });
    final prefs = await SharedPreferences.getInstance();
    final state = AppState(repo, prefs);
    expect(state.currentId, active);
    expect(state.masteryOf(archived), 2);
    expect(state.favs, contains(archived));
    expect(state.favoritePoems.map((p) => p.id), [active]);
    expect(state.countMastery(2), 0);
    state.pageController.dispose();
    state.dispose();
  });

  test('旧学习记录保留，停用篇目不进入收藏列表、统计、复习或当前阅读', () async {
    final disabled = (raw['disabledEntries'] as List).first['id'] as String;
    final active = repo.items.first.id;
    SharedPreferences.setMockInitialValues({
      'current_poem_id': disabled,
      'favs': [disabled, active],
      'mastery_map': jsonEncode({disabled: 2, active: 1}),
    });
    final prefs = await SharedPreferences.getInstance();
    final state = AppState(repo, prefs);
    expect(state.currentPoem, isNotNull);
    expect(state.currentId, isNot(disabled));
    expect(state.favs, contains(disabled));
    expect(state.masteryOf(disabled), 2);
    expect(state.favoritePoems.map((p) => p.id), [active]);
    expect(state.countMastery(2), 0);
    expect(state.countMastery(1), 1);
    expect(state.randomFromMastery(2), isNull);
    expect(state.poemsByMastery(2), isEmpty);
    expect(state.poolOf('古文'), isNot(contains(disabled)));
    state.pageController.dispose();
    state.dispose();
  });
}
