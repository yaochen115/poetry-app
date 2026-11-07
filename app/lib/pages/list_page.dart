import 'package:flutter/material.dart';

import '../scope.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// 掌握度列表（初习 / 熟习），点击直达首页。
class ListPage extends StatelessWidget {
  final int mastery;
  final String title;
  const ListPage({super.key, required this.mastery, required this.title});

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    final poems = state.poemsByMastery(mastery);

    return SwipeBack(
      child: Scaffold(
        backgroundColor: HzColors.of(context).bg,
        body: SafeArea(
          child: Column(
            children: [
              PageTopBar(title: title),
              Expanded(
                child: poems.isEmpty
                    ? const EmptyHint(text: '这一档还没有诗词')
                    : ListView(
                        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
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
