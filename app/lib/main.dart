import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';
import 'pages/home_page.dart';
import 'pages/me_page.dart';
import 'scope.dart';
import 'state.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final poemsJson = await rootBundle.loadString('assets/data/poems.json');
  final dictJson = await rootBundle.loadString('assets/data/dict.json');
  final repo = Repo.fromJson(poemsJson, dictJson);
  final state = AppState(repo, prefs);
  runApp(HzApp(state: state));
}

/// 根组件：StateScope 包住 MaterialApp，全局 navigatorKey 供首页跳转用。
class HzApp extends StatelessWidget {
  final AppState state;
  const HzApp({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    return StateScope(
      state: state,
      child: ListenableBuilder(
        listenable: state,
        builder: (context, child) => MaterialApp(
          navigatorKey: navigatorKey,
          title: '红妆',
          debugShowCheckedModeBanner: false,
          theme: buildTheme(),
          darkTheme: buildTheme(brightness: Brightness.dark),
          themeMode: state.darkMode ? ThemeMode.dark : ThemeMode.light,
          scrollBehavior: const NoGlowScrollBehavior(),
          builder: (context, child) {
            final dark = Theme.of(context).brightness == Brightness.dark;
            return AnnotatedRegion<SystemUiOverlayStyle>(
              value: SystemUiOverlayStyle(
                statusBarColor: Colors.transparent,
                statusBarIconBrightness: dark
                    ? Brightness.light
                    : Brightness.dark,
                statusBarBrightness: dark ? Brightness.dark : Brightness.light,
                systemNavigationBarColor: HzColors.of(context).bg,
                systemNavigationBarIconBrightness: dark
                    ? Brightness.light
                    : Brightness.dark,
              ),
              child: child!,
            );
          },
          home: const RootScreen(),
        ),
      ),
    );
  }
}

/// 首页 ↔ 我的 左右滑动，底部双点指示。
class RootScreen extends StatefulWidget {
  const RootScreen({super.key});

  @override
  State<RootScreen> createState() => _RootScreenState();
}

class _RootScreenState extends State<RootScreen> {
  int _page = 0;
  late final PageController _pageController;

  @override
  void initState() {
    super.initState();
    _pageController = StateScope.read(context).pageController;
    _pageController.addListener(_onPage);
  }

  @override
  void dispose() {
    _pageController.removeListener(_onPage);
    super.dispose();
  }

  void _onPage() {
    final pc = _pageController;
    if (!pc.hasClients) return;
    final p = pc.page?.round() ?? 0;
    if (p != _page) setState(() => _page = p);
  }

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    return Scaffold(
      backgroundColor: HzColors.of(context).bg,
      body: Stack(
        children: [
          PageView(
            controller: state.pageController,
            physics: const ClampingScrollPhysics(),
            children: const [HomePage(), MePage()],
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 14,
            child: IgnorePointer(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _Dot(on: _page == 0),
                  const SizedBox(width: 6),
                  _Dot(on: _page == 1),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Dot extends StatelessWidget {
  final bool on;
  const _Dot({required this.on});

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      width: on ? 18 : 6,
      height: 6,
      decoration: BoxDecoration(
        color: on ? HzColors.of(context).ink : HzColors.of(context).ink3,
        borderRadius: BorderRadius.circular(3),
      ),
    );
  }
}
