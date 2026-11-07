import 'package:flutter/material.dart';

import '../models.dart';
import '../scope.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// 查阅页：搜索标题 / 作者 / 朝代体裁 / 正文句子；点击结果直接显示在首页。
class SearchPage extends StatefulWidget {
  const SearchPage({super.key});

  @override
  State<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  final TextEditingController _controller = TextEditingController();
  List<Poem> _results = const [];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _search(String q) {
    final state = StateScope.read(context);
    q = q.trim();
    if (q.isEmpty) {
      setState(() => _results = const []);
      return;
    }
    final scored = <Poem, int>{};
    for (final p in state.repo.items) {
      var score = 0;
      if (p.title.contains(q)) score += 30;
      if (p.author.contains(q)) score += 20;
      if ('${p.dynasty}${p.category}${p.tags.join('')}'.contains(q)) {
        score += 10;
      }
      if (p.content.contains(q)) score += 5;
      if (score > 0) scored[p] = score;
    }
    final list = scored.keys.toList()
      ..sort((a, b) => (scored[b] ?? 0).compareTo(scored[a] ?? 0));
    setState(() => _results = list);
  }

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    return SwipeBack(
      child: Scaffold(
        backgroundColor: HzColors.of(context).bg,
        body: SafeArea(
          child: Column(
            children: [
              const PageTopBar(title: '查阅'),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 9,
                  ),
                  decoration: BoxDecoration(
                    color: HzColors.of(context).card,
                    border: Border.all(color: HzColors.of(context).line),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.search,
                        size: 17,
                        color: HzColors.of(context).ink3,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: _controller,
                          onChanged: _search,
                          style: TextStyle(
                            fontSize: 14,
                            color: HzColors.of(context).ink,
                          ),
                          decoration: const InputDecoration(
                            isDense: true,
                            border: InputBorder.none,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Expanded(
                child: _controller.text.trim().isEmpty
                    ? const SizedBox.shrink()
                    : _results.isEmpty
                    ? const EmptyHint(text: '没有找到相关内容')
                    : ListView(
                        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
                        children: [
                          for (final p in _results)
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
