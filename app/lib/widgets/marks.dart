import 'package:flutter/material.dart';

import '../theme.dart';

/// 三档掌握度圆圈标记：0 空圈 / 1 半满 / 2 实心。
class CircleMarkIcon extends StatelessWidget {
  final int state;
  final double size;
  final Color? border;
  final Color? fill;

  const CircleMarkIcon({
    super.key,
    required this.state,
    this.size = 19,
    this.border,
    this.fill,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _CircleMarkPainter(
          state,
          border ?? HzColors.of(context).btnBorder,
          fill ?? HzColors.of(context).ink,
        ),
      ),
    );
  }
}

class _CircleMarkPainter extends CustomPainter {
  final int state;
  final Color border;
  final Color fill;
  _CircleMarkPainter(this.state, this.border, this.fill);

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final r = size.width / 2 - 0.9;
    final bp = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.8
      ..color = border;
    canvas.drawCircle(c, r, bp);
    if (state == 0) return;
    final fp = Paint()
      ..style = PaintingStyle.fill
      ..color = fill;
    final fillR = r - 2.0;
    if (state == 1) {
      canvas.save();
      canvas.clipRect(Rect.fromLTRB(0, 0, size.width / 2, size.height));
      canvas.drawCircle(c, fillR, fp);
      canvas.restore();
    } else {
      canvas.drawCircle(c, fillR, fp);
    }
  }

  @override
  bool shouldRepaint(covariant _CircleMarkPainter old) =>
      old.state != state || old.border != border || old.fill != fill;
}

/// 底部掌握度按钮：默认收起为「当前掌握度」单图标，点击展开为三档按钮。
class MasteryBar extends StatefulWidget {
  final int current;
  final void Function(int v) onSelect;
  const MasteryBar({super.key, required this.current, required this.onSelect});

  @override
  State<MasteryBar> createState() => _MasteryBarState();
}

class _MasteryBarState extends State<MasteryBar> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    if (!_expanded) {
      return GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => setState(() => _expanded = true),
        child: SizedBox(
          height: 46,
          child: Center(child: CircleMarkIcon(state: widget.current, size: 26)),
        ),
      );
    }
    return Row(
      children: [
        for (var v = 0; v < 3; v++) ...[
          if (v > 0) const SizedBox(width: 12),
          Expanded(
            child: _MasteryButton(
              state: v,
              on: widget.current == v,
              onTap: () {
                setState(() => _expanded = false);
                widget.onSelect(v);
              },
            ),
          ),
        ],
      ],
    );
  }
}

/// 单个掌握度按钮：只显示圆圈图标（空圈 / 半满 / 实心），无文字。
class _MasteryButton extends StatelessWidget {
  final int state;
  final bool on;
  final VoidCallback onTap;
  const _MasteryButton({
    required this.state,
    required this.on,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final onInk = HzColors.of(context).onInk;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: 46,
        decoration: BoxDecoration(
          color: on ? HzColors.of(context).ink : HzColors.of(context).card,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: on ? HzColors.of(context).ink : HzColors.of(context).line,
          ),
        ),
        child: Center(
          child: CircleMarkIcon(
            state: state,
            size: 20,
            border: on ? onInk : HzColors.of(context).btnBorder,
            fill: on ? onInk : HzColors.of(context).ink,
          ),
        ),
      ),
    );
  }
}
