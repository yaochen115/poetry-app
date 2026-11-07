import 'package:flutter/material.dart';

import '../scope.dart';
import '../theme.dart';
import '../widgets/common.dart';

const List<String> _cats = ['唐诗', '宋词', '元曲', '古文'];
const List<String> _labels = ['诗', '词', '曲', '文'];

/// 类目页：按诗/词/曲/文分类浏览，点击直达首页。
class CatsPage extends StatefulWidget {
  const CatsPage({super.key});

  @override
  State<CatsPage> createState() => _CatsPageState();
}

class _CatsPageState extends State<CatsPage> {
  String _cat = ''; // 空串 = 全部

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    final poems = _cat.isEmpty
        ? state.repo.items
        : state.repo.items.where((p) => p.inCategory(_cat)).toList();

    return SwipeBack(
      child: Scaffold(
        backgroundColor: HzColors.of(context).bg,
        body: SafeArea(
          child: Column(
            children: [
              const PageTopBar(title: '类目'),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
                child: Row(
                  children: [
                    Expanded(
                      child: _CatPill(
                        label: '全部',
                        on: _cat.isEmpty,
                        onTap: () => setState(() => _cat = ''),
                      ),
                    ),
                    for (var i = 0; i < 4; i++) ...[
                      const SizedBox(width: 8),
                      Expanded(
                        child: _CatPill(
                          label: _labels[i],
                          on: _cat == _cats[i],
                          onTap: () => setState(() => _cat = _cats[i]),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              Expanded(
                child: ListView(
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

class _CatPill extends StatelessWidget {
  final String label;
  final bool on;
  final VoidCallback onTap;
  const _CatPill({required this.label, required this.on, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: 38,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: on ? HzColors.of(context).ink : HzColors.of(context).card,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: on ? HzColors.of(context).ink : HzColors.of(context).line,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            letterSpacing: 1,
            color: on ? HzColors.of(context).onInk : HzColors.of(context).ink2,
          ),
        ),
      ),
    );
  }
}
