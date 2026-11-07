import 'package:flutter/material.dart';

/// 「红妆」全局配色与主题。取自原型 index.html 的 CSS 变量。
class HzColors {
  const HzColors(this.isDark);

  final bool isDark;

  static HzColors of(BuildContext context) =>
      HzColors(Theme.of(context).brightness == Brightness.dark);

  Color get bg =>
      isDark ? const Color(0xFF171819) : const Color(0xFFFBF8F3); // 奶白底
  Color get card =>
      isDark ? const Color(0xFF222426) : const Color(0xFFFFFFFF); // 卡片
  Color get ink =>
      isDark ? const Color(0xFFE4DFD6) : const Color(0xFF2B2B2B); // 正文深墨灰
  Color get ink2 =>
      isDark ? const Color(0xFFB6AFA5) : const Color(0xFF8C857C); // 辅助浅墨灰
  Color get ink3 =>
      isDark ? const Color(0xFF8C857B) : const Color(0xFFB8B0A4); // 更浅墨灰
  Color get line =>
      isDark ? const Color(0xFF393B3D) : const Color(0xFFEDE6DA); // 分割线
  Color get chip =>
      isDark ? const Color(0xFF303234) : const Color(0xFFF3EEE4); // 浅奶白芯片
  Color get seal =>
      isDark ? const Color(0xFFC2B49F) : const Color(0xFF7A7263); // 印章线
  Color get sealBorder =>
      isDark ? const Color(0xFFA99B87) : const Color(0xFF9A8F7E); // 印章描边
  Color get markBg =>
      isDark ? const Color(0xFF464139) : const Color(0xFFEDE5D6); // 长按高亮
  Color get btnBorder =>
      isDark ? const Color(0xFFC9BFAF) : const Color(0xFF57524A); // 按钮描边
  Color get onInk => isDark ? const Color(0xFF202224) : const Color(0xFFF7F2E9);
}

/// 去掉 Android 默认的淡蓝色弧形回弹/发光限位特效（overscroll glow）。
class NoGlowScrollBehavior extends MaterialScrollBehavior {
  const NoGlowScrollBehavior();

  @override
  Widget buildOverscrollIndicator(
    BuildContext context,
    Widget child,
    ScrollableDetails details,
  ) {
    return child;
  }
}

ThemeData buildTheme({Brightness brightness = Brightness.light}) {
  final colors = HzColors(brightness == Brightness.dark);
  final base = ThemeData(
    useMaterial3: false,
    brightness: brightness,
    scaffoldBackgroundColor: colors.bg,
    fontFamilyFallback: const ['PingFang SC', 'Microsoft YaHei', 'sans-serif'],
    colorScheme: ColorScheme(
      brightness: brightness,
      primary: colors.ink,
      onPrimary: colors.onInk,
      secondary: colors.ink2,
      onSecondary: colors.onInk,
      error: brightness == Brightness.dark
          ? const Color(0xFFFFB4AB)
          : const Color(0xFFBA1A1A),
      onError: brightness == Brightness.dark
          ? const Color(0xFF690005)
          : Colors.white,
      surface: colors.bg,
      onSurface: colors.ink,
    ),
  );
  return base.copyWith(
    splashFactory: NoSplash.splashFactory,
    highlightColor: Colors.transparent,
    textTheme: base.textTheme.apply(
      bodyColor: colors.ink,
      displayColor: colors.ink,
    ),
  );
}
