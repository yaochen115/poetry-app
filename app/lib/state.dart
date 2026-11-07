import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

/// 全局导航 key，用于从任意页面「抽中后回到首页」。
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

/// 掌握度三档：0 未习 / 1 初习 / 2 熟习。
const List<String> masteryNames = ['未习', '初习', '熟习'];

class AppState extends ChangeNotifier {
  final Repo repo;
  final SharedPreferences prefs;
  final PageController pageController = PageController();

  final Map<String, int> _mastery = {};
  final List<String> _favs = [];
  String _currentId = '';
  int _reviewMastery = 0;
  bool _darkMode = false;

  AppState(this.repo, this.prefs) {
    _load();
  }

  void _load() {
    _currentId = prefs.getString('current_poem_id') ?? repo.items.first.id;
    final mm = prefs.getString('mastery_map');
    if (mm != null) {
      final m = jsonDecode(mm) as Map<String, dynamic>;
      m.forEach((k, v) => _mastery[k] = (v as num).toInt());
    }
    final ff = prefs.getStringList('favs');
    if (ff != null) _favs.addAll(ff);
    _reviewMastery = prefs.getInt('last_review_mastery') ?? 0;
    _darkMode = prefs.getBool('dark_mode') ?? false;
    if (!repo.byId.containsKey(_currentId)) {
      _currentId = repo.items.first.id;
    }
  }

  bool get darkMode => _darkMode;

  void setDarkMode(bool value) {
    if (_darkMode == value) return;
    _darkMode = value;
    prefs.setBool('dark_mode', value);
    notifyListeners();
  }

  String get currentId => _currentId;
  Poem? get currentPoem => repo.poem(_currentId);

  int masteryOf(String id) => _mastery[id] ?? 0;
  bool isFav(String id) => _favs.contains(id);
  int get reviewMastery => _reviewMastery;

  /// 收藏的 id（按收藏时间正序，越晚收藏越靠后）。
  List<String> get favs => List.unmodifiable(_favs);

  /// 收藏的诗词，倒序（最新收藏在前）。
  List<Poem> get favoritePoems {
    final r = <Poem>[];
    for (final id in _favs.reversed) {
      final p = repo.poem(id);
      if (p != null) r.add(p);
    }
    return r;
  }

  int countMastery(int ml) => _mastery.entries
      .where((e) => repo.byId.containsKey(e.key) && e.value == ml)
      .length;

  /// 某一档掌握度的全部诗词（未习 = 所有未标记或标为 0 的篇目）。
  List<Poem> poemsByMastery(int ml) {
    return repo.items.where((p) => masteryOf(p.id) == ml).toList();
  }

  /// 某一类中「未习」的诗词 id。
  List<String> poolOf(String category) => repo.items
      .where((p) => p.inCategory(category) && masteryOf(p.id) == 0)
      .map((p) => p.id)
      .toList();

  String? randomFromCategory(String category) {
    final pool = poolOf(category);
    if (pool.isEmpty) return null;
    return pool[Random().nextInt(pool.length)];
  }

  String? randomFromMastery(int ml) {
    final ids = _mastery.entries
        .where((e) => repo.byId.containsKey(e.key) && e.value == ml)
        .map((e) => e.key)
        .toList();
    if (ids.isEmpty) return null;
    return ids[Random().nextInt(ids.length)];
  }

  void setCurrent(String id) {
    if (!repo.byId.containsKey(id)) return;
    _currentId = id;
    prefs.setString('current_poem_id', id);
    notifyListeners();
  }

  void setMastery(String id, int v) {
    _mastery[id] = v;
    prefs.setString('mastery_map', jsonEncode(_mastery));
    notifyListeners();
  }

  void toggleFav(String id) {
    if (_favs.contains(id)) {
      _favs.remove(id);
    } else {
      _favs.add(id);
    }
    prefs.setStringList('favs', _favs);
    notifyListeners();
  }

  void setReviewMastery(int v) {
    _reviewMastery = v;
    prefs.setInt('last_review_mastery', v);
    notifyListeners();
  }

  /// 抽中一首 → 设为首页当前诗并回到首页（淡入过渡）。
  /// 等效打勾后随机抽中 / 类目点击 / 日省抽中。
  void homeSwap(String id) {
    setCurrent(id);
    if (pageController.hasClients) {
      pageController.animateToPage(
        0,
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOut,
      );
    }
    navigatorKey.currentState?.popUntil((r) => r.isFirst);
  }

  /// 长按查字典：返回需要展示的 [字/词, 拼音, 释义列表, 是否词命中]。
  /// 词优先：prev+ch 与 ch+next 两个双字组合命中即优先返回词义。
  DictionaryResult lookup(String ch, String prev, String next) {
    if (!_isHanzi(ch)) {
      return const DictionaryResult(
        head: '标点',
        pinyin: '',
        meanings: ['标点符号，用于断句与语气。'],
        isWord: false,
      );
    }
    if (repo.words.containsKey('$prev$ch')) {
      return DictionaryResult(
        head: '$prev$ch',
        pinyin: '',
        meanings: [repo.words['$prev$ch']!],
        isWord: true,
      );
    }
    if (repo.words.containsKey('$ch$next')) {
      return DictionaryResult(
        head: '$ch$next',
        pinyin: '',
        meanings: [repo.words['$ch$next']!],
        isWord: true,
      );
    }
    final e = repo.chars[ch];
    if (e != null) {
      final mns = <String>[...e.ancient, ...e.meanings];
      final py = e.pinyin.isEmpty ? '' : e.pinyin.join(' / ');
      return DictionaryResult(
        head: ch,
        pinyin: py,
        meanings: mns.isEmpty ? ['（未收录释义）'] : mns,
        isWord: false,
      );
    }
    return const DictionaryResult(
      head: '',
      pinyin: '',
      meanings: ['（未收录此字）'],
      isWord: false,
    );
  }

  bool _isHanzi(String ch) {
    if (ch.isEmpty) return false;
    final c = ch.codeUnitAt(0);
    return (c >= 0x4E00 && c <= 0x9FA5) || ch == '〇';
  }
}

class DictionaryResult {
  final String head; // 展示的大字（字或词）
  final String pinyin;
  final List<String> meanings;
  final bool isWord;
  const DictionaryResult({
    required this.head,
    required this.pinyin,
    required this.meanings,
    required this.isWord,
  });
}
