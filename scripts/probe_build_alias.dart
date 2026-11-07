import 'dart:io';

void main() {
  for (final p in [
    'R:/flutter-sdk/flutter',
    'R:/android-sdk',
    'R:/诗词软件/hongzhuang-project',
  ]) {
    print('$p => ${Directory(p).resolveSymbolicLinksSync()}');
  }
  print('cwd=${Directory.current.path}');
  print('executable=${Platform.resolvedExecutable}');
}
