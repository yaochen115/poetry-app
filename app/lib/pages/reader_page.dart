import 'package:flutter/material.dart';

import '../scope.dart';
import '../theme.dart';

/// 注释页：仅展示全文翻译；点击全屏任意位置返回首页。
class ReaderPage extends StatelessWidget {
  final String poemId;
  const ReaderPage({super.key, required this.poemId});

  @override
  Widget build(BuildContext context) {
    final state = StateScope.of(context);
    final poem = state.repo.poem(poemId);
    if (poem == null) {
      return Scaffold(
        backgroundColor: HzColors.of(context).bg,
        body: Center(
          child: Text(
            '未找到此篇',
            style: TextStyle(color: HzColors.of(context).ink2),
          ),
        ),
      );
    }
    final fav = state.isFav(poem.id);

    return Scaffold(
      backgroundColor: HzColors.of(context).bg,
      body: SafeArea(
        child: Stack(
          children: [
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => Navigator.of(context).pop(),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    // 每行开头空两格（　　），靠左；整块在屏幕垂直居中。
                    final translation = poem.translation.trim().isEmpty
                        ? '译文整理中'
                        : poem.translation;
                    final text = translation
                        .split('\n')
                        .map((l) {
                          final t = l.trim();
                          return t.isEmpty ? '' : '　　$t';
                        })
                        .join('\n');
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
                              padding: const EdgeInsets.fromLTRB(
                                30,
                                48,
                                30,
                                90,
                              ),
                              child: Text(
                                text,
                                style: TextStyle(
                                  fontSize: 15,
                                  height: 1.95,
                                  color: HzColors.of(context).ink,
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
            Positioned(
              top: 6,
              right: 6,
              child: GestureDetector(
                onTap: () => state.toggleFav(poem.id),
                behavior: HitTestBehavior.opaque,
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Icon(
                    fav ? Icons.bookmark : Icons.bookmark_border,
                    size: 22,
                    color: fav
                        ? HzColors.of(context).ink
                        : HzColors.of(context).ink2,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
