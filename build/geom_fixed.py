# Frozen per-page geometry, read from ruler overlays + clean detections.
# rows = list of y-centers of each box row (full-res px). cx = (x_left, x_right)
# spanning from the left edge of pair-1's reference box to the right edge of
# pair-3's write box. Layout is 3 [ref|write] pairs per row.
GEOM = {
 'img00': dict(cx=(158,1262), rows=[277,497,717,938,1158,1378,1600]),
 'img01': dict(cx=(162,1258), rows=[277,497,719,939,1163,1377,1598]),
 'img02': dict(cx=(154,1256), rows=[270,496,725,937,1157,1378,1598]),
 'img03': dict(cx=(146,1248), rows=[232,450]),
 'img04': dict(cx=(146,1268), rows=[348,570,792,1014,1230,1455,1673]),
 'img05': dict(cx=(156,1254), rows=[235,450]),
 'img06': dict(cx=(154,1262), rows=[248,470,692,914,1136,1358,1580]),
 'img07': dict(cx=(158,1252), rows=[235,450,770,990,1210,1425]),
 'img08': dict(cx=(142,1268), rows=[242,466,690,914,1138,1362,1586]),
 'img09': dict(cx=(142,1268), rows=[235,450,545]),
}
