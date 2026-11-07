import 'package:flutter/material.dart';

import '../flows.dart';
import '../models.dart';
import '../scope.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/common.dart';
import '../widgets/dict_sheet.dart';
import '../widgets/marks.dart';
import '../widgets/poem_text.dart';
import 'reader_page.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  void _openDict(
    BuildContext context,
    AppState state,
    String ch,
    String prev,
    String next,
  ) {
    showDictSheet(context, state.lookup(ch, prev, next));
  }

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    final poem = state.currentPoem;

    return Scaffold(
      backgroundColor: HzColors.of(context).bg,
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              // 点击首页空白/正文全屏均可进入注释页。
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => ReaderPage(poemId: state.currentId),
                  ),
                ),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    return SingleChildScrollView(
                      child: ConstrainedBox(
                        constraints: BoxConstraints(
                          minHeight: constraints.maxHeight,
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 30,
                                vertical: 24,
                              ),
                              child: poem == null
                                  ? const EmptyHint(text: '全部背完啦\n去「我的」页省己')
                                  : _HomeBody(
                                      key: ValueKey(poem.id),
                                      poem: poem,
                                      onLongPress: (ch, prev, next) =>
                                          _openDict(
                                            context,
                                            state,
                                            ch,
                                            prev,
                                            next,
                                          ),
                                    ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 26),
              child: MasteryBar(
                current: state.masteryOf(state.currentId),
                onSelect: (v) => markPoem(context, state, state.currentId, v),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HomeBody extends StatelessWidget {
  final Poem poem;
  final void Function(String ch, String prev, String next) onLongPress;

  const _HomeBody({super.key, required this.poem, required this.onLongPress});

  @override
  Widget build(BuildContext context) {
    final center = poem.isTang;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          poem.title,
          textAlign: center ? TextAlign.center : TextAlign.left,
          style: TextStyle(
            fontSize: 31,
            fontWeight: FontWeight.w600,
            letterSpacing: 1,
            height: 1.3,
            color: HzColors.of(context).ink,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          '${poem.author} · ${poem.dynasty}',
          textAlign: center ? TextAlign.center : TextAlign.left,
          style: TextStyle(fontSize: 16, color: HzColors.of(context).ink2),
        ),
        const SizedBox(height: 24),
        PoemText(
          content: poem.content,
          category: poem.category,
          fontSize: 24,
          lineHeight: 2.06,
          letterSpacing: 2,
          center: center,
          onLongPress: onLongPress,
        ),
      ],
    );
  }
}
