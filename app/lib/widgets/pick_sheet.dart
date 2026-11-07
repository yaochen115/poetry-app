import 'package:flutter/material.dart';

import '../state.dart';
import '../theme.dart';
import 'common.dart';

const List<String> _cats = ['唐诗', '宋词', '元曲', '古文'];
const List<String> _labels = ['诗', '词', '曲', '文'];

/// 打勾后弹出的四选一底部弹层（仅四个大字按钮，无标题/说明/计数）。
Future<void> showPickSheet(BuildContext context, AppState state) {
  return showModalBottomSheet(
    context: context,
    backgroundColor: HzColors.of(context).bg,
    barrierColor: const Color(0x61201D18),
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (ctx) => _PickSheet(state: state),
  );
}

class _PickSheet extends StatelessWidget {
  final AppState state;
  const _PickSheet({required this.state});

  void _pick(BuildContext ctx, String cat) {
    final id = state.randomFromCategory(cat);
    if (id == null) {
      showToast(ctx, '该类已无未习诗词');
      return;
    }
    Navigator.of(ctx).pop();
    state.homeSwap(id);
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(22, 10, 22, 22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4.5,
              decoration: BoxDecoration(
                color: HzColors.of(context).ink3,
                borderRadius: BorderRadius.circular(3),
              ),
            ),
            const SizedBox(height: 14),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 2.1,
              children: [
                for (var i = 0; i < 4; i++)
                  _PickButton(
                    label: _labels[i],
                    onTap: () => _pick(context, _cats[i]),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PickButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _PickButton({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: HzColors.of(context).card,
          border: Border.all(color: HzColors.of(context).line),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 21,
            fontWeight: FontWeight.w600,
            letterSpacing: 5,
            color: HzColors.of(context).ink,
          ),
        ),
      ),
    );
  }
}
