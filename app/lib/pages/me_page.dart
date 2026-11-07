import 'package:flutter/material.dart';

import '../scope.dart';
import '../theme.dart';
import 'cats_page.dart';
import 'favs_page.dart';
import 'list_page.dart';
import 'review_page.dart';
import 'search_page.dart';

class MePage extends StatelessWidget {
  const MePage({super.key});

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    return Scaffold(
      backgroundColor: HzColors.of(context).bg,
      body: SafeArea(
        child: Column(
          children: [
            Container(
              decoration: BoxDecoration(
                color: HzColors.of(context).card,
                border: Border(
                  bottom: BorderSide(color: HzColors.of(context).line),
                ),
              ),
              padding: const EdgeInsets.fromLTRB(22, 26, 22, 24),
              child: Column(
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: HzColors.of(context).sealBorder,
                        width: 2.5,
                      ),
                      borderRadius: BorderRadius.circular(9),
                    ),
                    child: Text(
                      '红\n妆',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 11,
                        color: HzColors.of(context).seal,
                        height: 1.3,
                        letterSpacing: 1,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _StatButton(
                        num: state.countMastery(1),
                        label: '初习',
                        onTap: () =>
                            _go(context, ListPage(mastery: 1, title: '初习')),
                      ),
                      const SizedBox(width: 46),
                      _StatButton(
                        num: state.countMastery(2),
                        label: '熟习',
                        onTap: () =>
                            _go(context, ListPage(mastery: 2, title: '熟习')),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 40),
                children: [
                  _EntryCard(
                    label: '查阅',
                    onTap: () => _go(context, const SearchPage()),
                  ),
                  const SizedBox(height: 12),
                  _EntryCard(
                    label: '类目',
                    onTap: () => _go(context, const CatsPage()),
                  ),
                  const SizedBox(height: 12),
                  _EntryCard(
                    label: '典藏',
                    onTap: () => _go(context, const FavsPage()),
                  ),
                  const SizedBox(height: 12),
                  _EntryCard(
                    label: '省己',
                    onTap: () => _go(context, const ReviewPage()),
                  ),

                ],
              ),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.only(right: 14, bottom: 20),
                child: IconButton(
                  key: const ValueKey('theme-toggle'),
                  tooltip: state.darkMode ? '切换浅色模式' : '切换黑夜模式',
                  iconSize: 21,
                  color: HzColors.of(context).ink2,
                  icon: Icon(state.darkMode
                      ? Icons.light_mode_outlined
                      : Icons.dark_mode_outlined),
                  onPressed: () => state.setDarkMode(!state.darkMode),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _go(BuildContext context, Widget page) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));
  }
}

class _StatButton extends StatelessWidget {
  final int num;
  final String label;
  final VoidCallback onTap;
  const _StatButton({
    required this.num,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Column(
          children: [
            Text(
              '$num',
              style: TextStyle(
                fontSize: 30,
                fontWeight: FontWeight.w600,
                color: HzColors.of(context).ink,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: HzColors.of(context).ink2,
                letterSpacing: 1,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EntryCard extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _EntryCard({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 18),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: HzColors.of(context).card,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [
            BoxShadow(
              color: Color(0x0F2B2B2B),
              blurRadius: 12,
              offset: Offset(0, 2),
            ),
          ],
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            letterSpacing: 2,
            color: HzColors.of(context).ink,
          ),
        ),
      ),
    );
  }
}
