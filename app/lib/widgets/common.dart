import 'package:flutter/material.dart';

import '../theme.dart';

/// 浮动 pill toast（原型底部居中样式）。
void showToast(BuildContext context, String msg) {
  final overlay = Overlay.of(context);
  late OverlayEntry entry;
  entry = OverlayEntry(
    builder: (_) => _ToastWidget(
      msg: msg,
      onDone: () {
        if (entry.mounted) entry.remove();
      },
    ),
  );
  overlay.insert(entry);
}

class _ToastWidget extends StatefulWidget {
  final String msg;
  final VoidCallback onDone;
  const _ToastWidget({required this.msg, required this.onDone});

  @override
  State<_ToastWidget> createState() => _ToastWidgetState();
}

class _ToastWidgetState extends State<_ToastWidget> {
  double _opacity = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) setState(() => _opacity = 1);
    });
    Future.delayed(const Duration(milliseconds: 1800), () {
      if (mounted) setState(() => _opacity = 0);
    });
    Future.delayed(const Duration(milliseconds: 2100), () {
      if (mounted) widget.onDone();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: 0,
      right: 0,
      bottom: 110,
      child: IgnorePointer(
        child: Center(
          child: AnimatedOpacity(
            opacity: _opacity,
            duration: const Duration(milliseconds: 250),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
              decoration: BoxDecoration(
                color: const Color(0xEB25221C),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                widget.msg,
                style: const TextStyle(
                  fontSize: 12.5,
                  color: Color(0xFFF6F1E7),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 子页面顶部栏：仅居中标题（无返回按钮，返回靠左→右滑动）。
class PageTopBar extends StatelessWidget {
  final String title;
  const PageTopBar({super.key, required this.title});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: HzColors.of(context).card,
        border: Border(bottom: BorderSide(color: HzColors.of(context).line)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      child: Center(
        child: Text(
          title,
          style: TextStyle(
            fontSize: 15.5,
            fontWeight: FontWeight.w600,
            color: HzColors.of(context).ink,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
    );
  }
}

/// 左→右滑动返回上一页（取代左上角返回按钮）。
class SwipeBack extends StatelessWidget {
  final Widget child;
  const SwipeBack({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onHorizontalDragEnd: (details) {
        final vx = details.velocity.pixelsPerSecond.dx;
        if (vx > 280) Navigator.of(context).maybePop();
      },
      child: child,
    );
  }
}

/// 列表条目（标题 + 作者·朝代）。
class PoemItem extends StatelessWidget {
  final String title;
  final String by;
  final VoidCallback onTap;
  const PoemItem({
    super.key,
    required this.title,
    required this.by,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        margin: const EdgeInsets.only(top: 12),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        decoration: BoxDecoration(
          color: HzColors.of(context).card,
          borderRadius: BorderRadius.circular(14),
          boxShadow: const [
            BoxShadow(
              color: Color(0x0F2B2B2B),
              blurRadius: 12,
              offset: Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: HzColors.of(context).ink,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 3),
            Text(
              by,
              style: TextStyle(
                fontSize: 11.5,
                color: HzColors.of(context).ink2,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

/// 空状态提示。
class EmptyHint extends StatelessWidget {
  final String text;
  const EmptyHint({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 60),
      child: Center(
        child: Text(
          text,
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 14,
            color: HzColors.of(context).ink2,
            height: 2,
          ),
        ),
      ),
    );
  }
}
