import 'package:flutter/material.dart';

import '../scope.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// 省己页：选一档掌握度，「日省」随机抽一首；其下显示该档全部诗词，点击直达首页。
class ReviewPage extends StatefulWidget {
  const ReviewPage({super.key});

  @override
  State<ReviewPage> createState() => _ReviewPageState();
}

class _ReviewPageState extends State<ReviewPage> {
  int _ml = 1; // 仅初习 / 熟习两档

  void _doReview() {
    final state = StateScope.read(context);
    final id = state.randomFromMastery(_ml);
    if (id == null) {
      showToast(context, '这一档还没有诗词');
      return;
    }
    state.homeSwap(id);
  }

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    final poems = state.poemsByMastery(_ml);

    return SwipeBack(
      child: Scaffold(
        backgroundColor: HzColors.of(context).bg,
        body: SafeArea(
          child: Column(
            children: [
              const PageTopBar(title: '省己'),
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 28, 24, 0),
                child: Row(
                  children: [
                    for (var ml = 1; ml < 3; ml++) ...[
                      if (ml > 1) const SizedBox(width: 10),
                      Expanded(
                        child: _Seg(
                          label: masteryNames[ml],
                          on: _ml == ml,
                          onTap: () => setState(() => _ml = ml),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
                child: GestureDetector(
                  onTap: _doReview,
                  behavior: HitTestBehavior.opaque,
                  child: Container(
                    width: double.infinity,
                    height: 50,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: HzColors.of(context).ink,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      '日省',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 3,
                        color: HzColors.of(context).onInk,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: poems.isEmpty
                    ? const EmptyHint(text: '这一档还没有诗词')
                    : ListView(
                        padding: const EdgeInsets.fromLTRB(20, 0, 20, 40),
                        children: [
                          for (final p in poems)
                            PoemItem(
                              title: p.title,
                              by: '${p.author} · ${p.dynasty}',
                              onTap: () => state.homeSwap(p.id),
                            ),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Seg extends StatelessWidget {
  final String label;
  final bool on;
  final VoidCallback onTap;
  const _Seg({required this.label, required this.on, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: 42,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: on ? HzColors.of(context).ink : HzColors.of(context).card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: on ? HzColors.of(context).ink : HzColors.of(context).line,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            letterSpacing: 2,
            color: on ? HzColors.of(context).onInk : HzColors.of(context).ink2,
          ),
        ),
      ),
    );
  }
}
