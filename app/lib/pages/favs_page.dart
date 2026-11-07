import 'package:flutter/material.dart';

import '../scope.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// 典藏页：收藏列表（按收藏时间倒序），点击直达首页。
class FavsPage extends StatelessWidget {
  const FavsPage({super.key});

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    final poems = state.favoritePoems;
    return SwipeBack(
      child: Scaffold(
        backgroundColor: HzColors.of(context).bg,
        body: SafeArea(
          child: Column(
            children: [
              const PageTopBar(title: '典藏'),
              Expanded(
                child: poems.isEmpty
                    ? const EmptyHint(text: '还没有收藏的诗词')
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
