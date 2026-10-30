# ia-toolbox

## 0.2.0

### Minor Changes

- 3118874: A document that needs a password to open is now reported as password-protected,
  in French and English, instead of as a generic processing failure telling you to
  check file and folder access — advice that could not help, since the file is
  readable and no permission is missing. The original file is left untouched and
  the rest of the batch continues.

  A document that is only locked against editing is not encrypted and still
  converts normally. Legacy `.xls` workbooks are the exception: a protected one is
  reported as unreadable.
