# Debouncing

Editors often write a file several times in a row. tidewatch waits until a
watch has been quiet for the debounce window, then runs its hook once, with the
last change it saw.
