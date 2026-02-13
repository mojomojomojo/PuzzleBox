#ifdef __APPLE__

# define strdupa(s)                                                              \
	  (__extension__                                                              \
	       ({                                                                              \
			      const char *__old = (s);                                                      \
			      size_t __len = strlen (__old) + 1;                                      \
			      char *__new = (char *) __builtin_alloca (__len);                              \
			      (char *) memcpy (__new, __old, __len);                                      \
			    }))

#endif // __APPLE__

#ifndef __APPLE__
/* Fallback for non-Apple platforms: map strdupa to strdup (heap allocation).
	Note: original strdupa uses alloca; using strdup is acceptable here. */
# include <string.h>
# include <stdlib.h>
# ifndef strdupa
#  define strdupa(s) strdup(s)
# endif
#endif
