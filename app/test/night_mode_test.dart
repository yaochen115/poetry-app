import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:hongzhuang_app/main.dart';
import 'package:hongzhuang_app/models.dart';
import 'package:hongzhuang_app/pages/reader_page.dart';
import 'package:hongzhuang_app/state.dart';
import 'package:hongzhuang_app/widgets/dict_sheet.dart';

Repo sampleRepo() => Repo.fromJson(
  '{"items":[{"id":"tang-001","title":"静夜思","author":"李白",'
      '"category":"唐诗","content":"床前明月光。","translation":"床前洒满月光。"}]}',
  '{"chars":{},"words":{}}',
);

void main() {
  testWidgets('我的页面切换主题，立即更新配色并在重建状态时恢复选择', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final state = AppState(sampleRepo(), prefs);
    await tester.pumpWidget(HzApp(state: state));
    await tester.pumpAndSettle();
    expect(state.darkMode, isFalse);

    state.pageController.jumpToPage(1);
    await tester.pumpAndSettle();
    expect(find.byType(SwitchListTile), findsNothing);
    await tester.tap(find.byKey(const ValueKey('theme-toggle')));
    await tester.pumpAndSettle();

    expect(
      Theme.of(tester.element(find.byKey(const ValueKey('theme-toggle')))).brightness,
      Brightness.dark,
    );
    expect(prefs.getBool('dark_mode'), isTrue);
    expect(AppState(sampleRepo(), prefs).darkMode, isTrue);
    expect(
      tester.widget<Text>(find.text('查阅')).style!.color,
      const Color(0xFFE4DFD6),
    );
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const ValueKey('theme-toggle')));
    await tester.pumpAndSettle();
    expect(
      Theme.of(tester.element(find.byKey(const ValueKey('theme-toggle')))).brightness,
      Brightness.light,
    );
    expect(AppState(sampleRepo(), prefs).darkMode, isFalse);
    expect(
      tester.widget<Text>(find.text('查阅')).style!.color,
      const Color(0xFF2B2B2B),
    );
  });

  testWidgets('已保存的黑夜模式应用到译文和词典弹层', (tester) async {
    SharedPreferences.setMockInitialValues({'dark_mode': true});
    final state = AppState(sampleRepo(), await SharedPreferences.getInstance());
    await tester.pumpWidget(HzApp(state: state));
    await tester.pumpAndSettle();

    navigatorKey.currentState!.push(
      MaterialPageRoute<void>(
        builder: (_) => const ReaderPage(poemId: 'tang-001'),
      ),
    );
    await tester.pumpAndSettle();
    final translation = find.textContaining('床前洒满月光');
    expect(
      tester.widget<Text>(translation).style!.color,
      const Color(0xFFE4DFD6),
    );
    expect(Theme.of(tester.element(translation)).brightness, Brightness.dark);

    showDictSheet(
      tester.element(translation),
      DictionaryResult(
        head: '光',
        pinyin: 'guang1',
        meanings: ['光亮'],
        isWord: false,
      ),
    );
    await tester.pumpAndSettle();
    expect(
      tester.widget<Text>(find.text('光亮')).style!.color,
      const Color(0xFFE4DFD6),
    );
    expect(tester.takeException(), isNull);
  });
}
