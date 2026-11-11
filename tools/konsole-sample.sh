#!/bin/sh
printf '%s\n' \
  'Fontreal: real Konsole text' \
  '' \
  'Open the menus to inspect the selected sans font.' \
  "Initial terminal font: ${1:-built-in fixed-pitch font}." \
  'The title bar belongs to KWin and is a later test.' \
  '' \
  'Illl1|  minimum  moon  m n o g  lllm' \
  'W V w v   WWWV wwv   () [] {} / \\' \
  'The quick brown fox jumps over the lazy dog.' \
  '0123456789  () [] {} / \\ + = * - _' \
  '' \
  'Use View > Enlarge Font / Shrink Font to test terminal text.' \
  'Close this window when the comparison is complete.'
