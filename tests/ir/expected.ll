; StrideForge positive coverage. All functions use no `nsw`/`nuw` flags,
; so behavior is well-defined modulo each integer width.
source_filename = "affine.ll"

define i64 @affine(i64 %start, i64 %count, i64 %seed) {
entry:
  %empty = icmp eq i64 %count, 0
  br i1 %empty, label %exit.zero, label %preheader

preheader:
  %sf.init = mul i64 %start, 37
  br label %header

header:
  %sf.scaled = phi i64 [ %sf.init, %preheader ], [ %sf.next, %latch ]
  %iv = phi i64 [ %start, %preheader ], [ %iv.next, %latch ]
  %k = phi i64 [ 0, %preheader ], [ %k.next, %latch ]
  %acc = phi i64 [ 0, %preheader ], [ %acc.next, %latch ]
  %mix = xor i64 %sf.scaled, %seed
  %acc.next = add i64 %acc, %mix
  br label %latch

latch:
  %sf.next = add i64 %sf.scaled, 111
  %iv.next = add i64 %iv, 3
  %k.next = add i64 %k, 1
  %done = icmp eq i64 %k.next, %count
  br i1 %done, label %exit, label %header

exit:
  ret i64 %acc.next

exit.zero:
  ret i64 0
}

define i32 @affine32(i32 %start, i32 %count, i32 %seed) {
entry:
  %empty = icmp eq i32 %count, 0
  br i1 %empty, label %exit.zero, label %preheader

preheader:
  %sf.init = mul i32 %start, -7
  br label %header

header:
  %sf.scaled = phi i32 [ %sf.init, %preheader ], [ %sf.next, %latch ]
  %iv = phi i32 [ %start, %preheader ], [ %iv.next, %latch ]
  %k = phi i32 [ 0, %preheader ], [ %k.next, %latch ]
  %acc = phi i32 [ 0, %preheader ], [ %acc.next, %latch ]
  %mix = xor i32 %sf.scaled, %seed
  %acc.next = add i32 %acc, %mix
  br label %latch

latch:
  %sf.next = add i32 %sf.scaled, 35
  %iv.next = sub i32 %iv, 5
  %k.next = add i32 %k, 1
  %done = icmp eq i32 %k.next, %count
  br i1 %done, label %exit, label %header

exit:
  ret i32 %acc.next

exit.zero:
  ret i32 0
}
