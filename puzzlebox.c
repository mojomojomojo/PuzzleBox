// Puzzle box maker
// (c) 2018 Adrian Kennard www.me.uk @TheRealRevK
// This includes a distinctive "A" in the design at the final park point, otherwise there are no loops in the maze
// Please leave the "A" in the design as a distinctive feature

#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <popt.h>
#include <err.h>
#include <stdlib.h>
#include <ctype.h>
#include <math.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <time.h>
#include "apple-strdupa.h"

// Flags for maze array
#define	FLAGL 0x01              // Left
#define FLAGR 0x02              // Right
#define FLAGU 0x04              // Up
#define FLAGD 0x08              // Down
#define	FLAGA 0x0F              // All directions
#define	FLAGI 0x80              // Invalid

#define	BIASL	2               // Direction bias for random maze choices
#define	BIASR	1
#define	BIASU	1
#define	BIASD	4

#define	SCALE 1000LL            // Scales used for some aspects of output
#define	SCALEI "0.001"
#define	scaled(x)	((long long)round((x)*SCALE))

/**
 * Main entry point for the puzzle box generator.
 * Parses command line arguments, validates parameters, generates OpenSCAD code
 * for 3D-printable cylindrical maze puzzle boxes, and optionally converts to STL.
 * 
 * @param argc Number of command line arguments
 * @param argv Array of command line argument strings
 * @return 0 on success, 1 on error
 */
int
main (int argc, const char *argv[])
{
   double basethickness = 1.6;
   double basegap = 0.4;
   double baseheight = 10;
   double corediameter = 30;
   double coreheight = 50;
   double wallthickness = 1.2;
   double mazethickness = 2;
   double mazestep = 3;
   double clearance = 0.4;      // General X/Y clearance for parts
   double nubrclearance = 0.1;  // Extra radius clearance for nub, should be less than clearance, can be -ve
   double nubzclearance = 0.2;  // Extra Z clearance (per /4 maze step)
   double nubhorizontal = 1.0;  // Nub horizontal (circumferential) size multiplier
   double nubvertical = 1.0;    // Nub vertical (height) size multiplier
   double nubnormal = 1.0;      // Nub normal (radial depth) size multiplier
   double parkthickness = 0.7;
   double coregap = 0;
   double outerround = 2;
   double mazemargin = 1;
   double textdepth = 0.5;
   double logodepth = 0.6;
   double gripdepth = 1.5;
   double textsidescale = 100;
   char *textinside = NULL;
   char *textend = NULL;
   char *textsides = NULL;
   char *textfont = NULL;
   char *textfontend = NULL;
   int parts = 2;
   int part = 0;
   int inside = 0;
   int flip = 0;
   int outersides = 7;
   int testmaze = 0;
   int helix = 2;
   int nubs = helix;
   int aalogo = 0;
   int ajklogo = 0;
   int textslow = 0;
   int textoutset = 0;
   int symmectriccut = 0;
   int coresolid = 0;
   int mime = (getenv ("HTTP_HOST") ? 1 : 0);
   int webform = 0;
   int parkvertical = 0;
   int mazecomplexity = 5;
   int mirrorinside = 0;        // Clockwise lock on inside - may be unwise as more likely to come undone with outer.
   int fixnubs = 0;             // Fix nub position opposite maze exit
   double globalexit = 0;       // Global maze exit angle (for fix-nubs across all parts)
   char *mazedata = NULL;       // Buffer to store maze visualization data for STL comments
   size_t mazedatasize = 0;     // Current size of maze data buffer
   size_t mazedatacap = 0;      // Capacity of maze data buffer
   int noa = 0;
   int basewide = 0;
   int stl = 0;
   int resin = 0;
   const char *outfile = NULL;

   int f = open ("/dev/urandom", O_RDONLY);
   if (f < 0)
      err (1, "Open /dev/random");

   char pathsep = 0;
   char *path = getenv ("PATH_INFO");
   if (path)
      pathsep = '/';
   else if ((path = getenv ("QUERY_STRING")))
      pathsep = '&';

   const struct poptOption optionsTable[] = {
      {"stl", 'l', POPT_ARG_NONE, &stl, 0, "Run output through openscad to make stl (may take a few seconds)"},
      {"resin", 'R', POPT_ARG_NONE, &resin, 0, "Half all specified clearances for resin printing"},
      {"parts", 'm', POPT_ARG_INT | POPT_ARGFLAG_SHOW_DEFAULT, &parts, 0, "Total parts", "N"},
      {"core-diameter", 'c', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &corediameter, 0, "Core diameter for content", "mm"},
      {"core-height", 'h', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &coreheight, 0, "Core height for content", "mm"},
      {"core-gap", 'C', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &coregap, 0, "Core gap to allow content to be removed", "mm"},
      {"text-end", 'E', POPT_ARG_STRING | (textend ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &textend, 0, "Text (initials) on end",
       "X{\\X...}"},
      {"text-inside", 'I', POPT_ARG_STRING | (textinside ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &textinside, 0,
       "Text (initials) inside end", "X{\\X...}"},
      {"text-side", 'S', POPT_ARG_STRING | (textsides ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &textsides, 0, "Text on sides",
       "Text{\\Text...}"},
      {"part", 'n', POPT_ARG_INT, &part, 0, "Which part to make", "N (0 for all)"},
      {"inside", 'i', POPT_ARG_NONE, &inside, 0, "Maze on inside (hard)"},
      {"flip", 'f', POPT_ARG_NONE, &flip, 0, "Alternating inside/outside maze"},
      {"nubs", 'N', POPT_ARG_INT | POPT_ARGFLAG_SHOW_DEFAULT, &nubs, 0, "Nubs", "N"},
      {"helix", 'H', POPT_ARG_INT | POPT_ARGFLAG_SHOW_DEFAULT, &helix, 0, "Helix", "N (0 for non helical)"},
      {"base-height", 'b', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &baseheight, 0, "Base height", "mm"},
      {"core-solid", 'q', POPT_ARG_NONE, &coresolid, 0, "Core solid (content is in part 2)"},
      {"part-thickness", 'w', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &wallthickness, 0, "Wall thickness", "mm"},
      {"maze-thickness", 't', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &mazethickness, 0, "Maze thickness", "mm"},
      {"maze-step", 'z', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &mazestep, 0, "Maze spacing", "mm"},
      {"maze-margin", 'M', POPT_ARG_DOUBLE | (mazemargin ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &mazemargin, 0, "Maze top margin", "mm"},
      {"maze-complexity", 'X', POPT_ARG_INT | (mazecomplexity ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &mazecomplexity, 0,
       "Maze complexity", "-10 to 10"},
      {"park-thickness", 'p', POPT_ARG_DOUBLE | (parkthickness ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &parkthickness, 0,
       "Thickness of park ridge to click closed", "mm"},
      {"park-vertical", 'v', POPT_ARG_NONE, &parkvertical, 0, "Park vertically"},
      {"base-thickness", 'B', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &basethickness, 0, "Base thickness", "mm"},
      {"base-wide", 'W', POPT_ARG_NONE, &basewide, 0, "Inside base full width"},
      {"base-gap", 'Z', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &basegap, 0, "Base gap (Z clearance)", "mm"},
      {"clearance", 'g', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &clearance, 0, "General X/Y clearance", "mm"},
      {"nub-r-clearance", 'y', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &nubrclearance, 0, "Extra clearance on radius for nub",
       "mm"},
      {"nub-z-clearance", 'Z', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &nubzclearance, 0, "Extra clearance on height of nub",
       "mm"},
      {"nub-horizontal", 0, POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &nubhorizontal, 0, "Nub horizontal (circumferential) size multiplier",
       "factor"},
      {"nub-vertical", 0, POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &nubvertical, 0, "Nub vertical (height) size multiplier",
       "factor"},
      {"nub-normal", 0, POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &nubnormal, 0, "Nub normal (radial depth) size multiplier",
       "factor"},
      {"fix-nubs", 0, POPT_ARG_NONE, &fixnubs, 0, "Fix nub position opposite maze exit"},
      {"outer-sides", 's', POPT_ARG_INT | (outersides ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &outersides, 0, "Number of outer sides",
       "N (0=round)"},
      {"outer-round", 'r', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &outerround, 0, "Outer rounding on ends", "mm"},
      {"grip-depth", 'G', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &gripdepth, 0, "Grip depth", "mm"},
      {"text-depth", 'D', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &textdepth, 0, "Text depth", "mm"},
      {"text-font", 'F', POPT_ARG_STRING | (textfont ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &textfont, 0, "Text font (optional)",
       "Font"},
      {"text-font-end", 'e', POPT_ARG_STRING | (textfontend ? POPT_ARGFLAG_SHOW_DEFAULT : 0), &textfontend, 0,
       "Text font for end (optional)", "Font"},
      {"text-slow", 'd', POPT_ARG_NONE, &textslow, 0, "Text has diagonal edges"},
      {"text-side-scale", 'T', POPT_ARG_DOUBLE, &textsidescale, 0, "Scale side text (i.e. if too long)", "%"},
      {"text-outset", 'O', POPT_ARG_NONE, &textoutset, 0, "Text on sides is outset not embossed"},
      {"logo-depth", 'L', POPT_ARG_DOUBLE | POPT_ARGFLAG_SHOW_DEFAULT, &logodepth, 0, "Logo (and inside text) cut depth", "mm"},
      {"symmetric-cut", 'V', POPT_ARG_NONE, &symmectriccut, 0, "Symmetric maze cut"},
      {"ajk-logo", 'A', POPT_ARG_NONE, &ajklogo, 0, "Include AJK logo in last lid (not for sale, on tasteful designs)"},
      {"aa-logo", 'a', POPT_ARG_NONE, &aalogo, 0, "Include A&A logo in last lid (not for sale, on tasteful designs)"},
      {"test", 'Q', POPT_ARG_NONE, &testmaze, 0, "Test pattern instead of maze"},
      {"mime", 0, POPT_ARG_NONE | (mime ? POPT_ARGFLAG_DOC_HIDDEN : 0), &mime, 0, "MIME Header"},
      {"no-a", 0, POPT_ARG_NONE | (noa ? POPT_ARGFLAG_DOC_HIDDEN : 0), &noa, 0, "No A"},
      {"web-form", 0, POPT_ARG_NONE, &webform, 0, "Web form"},
      {"out-file", 0, POPT_ARG_STRING, &outfile, 0, "Output to file", "filename"},
      POPT_AUTOHELP {}
   };

   {                            // POPT
      poptContext optCon;       // context for parsing command-line options

      optCon = poptGetContext (NULL, argc, argv, optionsTable, 0);
      //poptSetOtherOptionHelp (optCon, "");

      int c;
      if ((c = poptGetNextOpt (optCon)) < -1)
         errx (1, "%s: %s\n", poptBadOption (optCon, POPT_BADOPTION_NOALIAS), poptStrerror (c));

      if (poptPeekArg (optCon))
      {
         poptPrintUsage (optCon, stderr, 0);
         return -1;
      }
      poptFreeContext (optCon);
   }

   if (resin)
   {                            // Lower clearances for resin print
      basegap /= 2;
      clearance /= 2;
      nubrclearance /= 2;
      nubzclearance /= 2;
   }

   char *error = NULL;
   if (path)
   {                            // Settings from PATH_INFO
      path = strdupa (path);
      while (*path)
      {
         if (*path == pathsep)
         {
            *path++ = 0;
            continue;
         }
         if (!isalpha (*path))
         {
            if (asprintf (&error, "Path error [%s]\n", path) < 0)
               errx (1, "malloc");
            break;
         }
         char arg = *path++;
         int o;
         for (o = 0; optionsTable[o].longName && optionsTable[o].shortName != arg; o++);
         if (!optionsTable[o].shortName)
         {
            if (asprintf (&error, "Unknown arg [%c]", arg) < 0)
               errx (1, "malloc");
            break;
         }
         if (optionsTable[o].arg)
            switch (optionsTable[o].argInfo & POPT_ARG_MASK)
            {
            case POPT_ARG_INT:
               if (*path != '=')
               {
                  if (asprintf (&error, "Missing value [%c=]", arg) < 0)
                     errx (1, "malloc");
                  break;
               }
               if (path[1])
                  *(int *) optionsTable[o].arg = strtod (path + 1, &path);
               break;
            case POPT_ARG_DOUBLE:
               if (*path != '=')
               {
                  if (asprintf (&error, "Missing value [%c=]", arg) < 0)
                     errx (1, "malloc");
                  break;
               }
               if (path[1])
                  *(double *) optionsTable[o].arg = strtod (path + 1, &path);
               break;
            case POPT_ARG_NONE:
               *(int *) optionsTable[o].arg = 1;
               if (*path == '=')
               {                // Skip =on, etc.
                  path++;
                  while (*path && *path != pathsep)
                     path++;
               }
               break;
            case POPT_ARG_STRING:
               if (*path != '=')
               {
                  if (asprintf (&error, "Missing value [%c=]", arg) < 0)
                     errx (1, "malloc");
                  break;
               }
               path++;
               *(char **) optionsTable[o].arg = path;
               char *o = path;
               while (*path && *path != pathsep)
               {
                  if (pathsep == '&' && *path == '+')
                     *o++ = ' ';
                  else if (pathsep == '&' && *path == '%' && isxdigit (path[1]) && isxdigit (path[2]))
                  {
                     *o++ =
                        (((isalpha (path[1]) ? 9 : 0) + (path[1] & 0xF)) << 4) + ((isalpha (path[2]) ? 9 : 0) + (path[2] & 0xF));
                     path += 2;
                  } else
                     *o++ = *path;
                  path++;
               }
               if (o < path)
                  *o = 0;
               break;
            }
      }
   }

   if (webform)
   {
      int o;
      for (o = 0; optionsTable[o].longName; o++)
         if (optionsTable[o].shortName && optionsTable[o].arg)
         {
            printf ("<tr>");
            printf ("<td><label for='%c'>%c%s</label></td>", optionsTable[o].shortName, optionsTable[o].shortName,
                    (optionsTable[o].argInfo & POPT_ARG_MASK) == POPT_ARG_NONE ? "" : "=");
            printf ("<td>");
            switch (optionsTable[o].argInfo & POPT_ARG_MASK)
            {
            case POPT_ARG_NONE:        // Checkbox
               printf ("<input type=checkbox id='%c' name='%c'%s/>", optionsTable[o].shortName, optionsTable[o].shortName,
                       strchr ("ldA", optionsTable[o].shortName) ? " checked" : "");
               break;
            case POPT_ARG_INT: // Select
               {
                  int l = 0,
                     h = 3,
                     v = *(int *) optionsTable[o].arg;
                  if (optionsTable[o].shortName == 'N')
                     l = 1;     // Nubs
                  if (optionsTable[o].shortName == 'm')
                     l = 2;     // Walls
                  if (optionsTable[o].shortName == 'n' || optionsTable[o].shortName == 'm')
                     h = 6;     // Walls or part
                  if (optionsTable[o].shortName == 's')
                     h = 20;    // Sides
                  if (optionsTable[o].shortName == 'X')
                  {             // Complexity
                     l = -10;
                     h = 10;
                  }
                  printf ("<select name='%c' id='%c'>", optionsTable[o].shortName, optionsTable[o].shortName);
                  for (; l <= h; l++)
                     printf ("<option value='%d'%s>%d</option>", l, l == v ? " selected" : "", l);
                  printf ("</select>");
               }
               break;
            case POPT_ARG_DOUBLE:      // Double
               {
                  double v = *(double *) optionsTable[o].arg;
                  printf ("<input size='5' name='%c' id='%c'", optionsTable[o].shortName, optionsTable[o].shortName);
                  if (v)
                  {
                     char temp[50],
                      *p;
                     sprintf (temp, "%f", v);
                     for (p = temp + strlen (temp); p > temp && p[-1] == '0'; p--);
                     if (p > temp && p[-1] == '.')
                        p--;
                     *p = 0;
                     printf (" value='%s'", temp);
                  }
                  printf ("/>");
               }
               break;
            case POPT_ARG_STRING:      // String
               {
                  char *v = *(char **) optionsTable[o].arg;
                  printf ("<input name='%c' id='%c'", optionsTable[o].shortName, optionsTable[o].shortName);
                  if (optionsTable[o].shortName == 'E' || optionsTable[o].shortName == 'I')
                     printf (" size='2'");      // Initials
                  if (v)
                     printf (" value='%s'", v);
                  printf ("/>");
               }
               break;
            }
            if (optionsTable[o].argDescrip)
               printf ("%s", optionsTable[o].argDescrip);
            printf ("</td>");
            printf ("<td><label for='%c'>%s</label></td>", optionsTable[o].shortName, optionsTable[o].descrip);
            printf ("</tr>\n");
         }
      return 0;
   }

   // Sanity checks and adjustments
   /**
    * Normalizes text input by replacing double quotes with single quotes.
    * Used to sanitize user-provided text for safe inclusion in OpenSCAD output.
    * 
    * @param t Input text string to normalize
    * @return Normalized text string, or NULL if input is NULL or empty
    */
   char *normalise (char *t)
   {                            // Simple text normalise
      if (!t || !*t)
         return NULL;
      char *text = t;
      while (*t)
      {
         if (*t == '"')
            *t == '\'';
         t++;
      }
      return text;
   }
   textend = normalise (textend);
   textsides = normalise (textsides);
   textinside = normalise (textinside);
   if (!outersides)
      textsides = NULL;
   if (textfont && !*textfont)
      textfont = NULL;
   if (textfont && !textfontend)
      textfontend = textfont;
   if (textend && !*textend)
      textend = NULL;
   if (textinside && !*textinside)
      textinside = NULL;
   if (textsides && !*textsides)
   {
      textsidescale = 0;
      textsides = NULL;
   }
   if (helix && nubs > 1 && nubs < helix)
   {
      if (!(helix % 2) && nubs <= helix / 2)
         nubs = helix / 2;
      else
         nubs = helix;
   }
   if (helix && nubs > helix)
      nubs = helix;
   if (gripdepth > (baseheight - outerround) / 5)
      gripdepth = (baseheight - outerround) / 5;
   if (gripdepth > mazethickness)
      gripdepth = mazethickness;
   if (!aalogo && !ajklogo && !textinside)
      logodepth = 0;
   if (!textsides && !textend && !textinside)
      textdepth = 0;
   if (coresolid && coregap < mazestep * 2)
      coregap = mazestep * 2;

   int markpos0 = (outersides && outersides / nubs * nubs != outersides);       // Mark on position zero for alignment
   double nubskew = (symmectriccut ? 0 : mazestep / 8); // Skew the shape of the cut

   // MIME header
   if (mime)
   {
      printf ("Content-Type: %s\r\nContent-Disposition: Attachment; filename=puzzlebox", stl ? "model/stl" : "application/scad");
      int o;
      for (o = 0; optionsTable[o].longName; o++)
         if (optionsTable[o].shortName && optionsTable[o].arg)
            switch (optionsTable[o].argInfo & POPT_ARG_MASK)
            {
            case POPT_ARG_NONE:
               if (!*(int *) optionsTable[o].arg)
                  break;
               printf ("-%c", optionsTable[o].shortName);
               break;
            case POPT_ARG_INT:
               if (!*(int *) optionsTable[o].arg)
                  break;
               printf ("-%d%c", *(int *) optionsTable[o].arg, optionsTable[o].shortName);
               break;
            case POPT_ARG_DOUBLE:
               if (!*(double *) optionsTable[o].arg)
                  break;
               char temp[50],
                *p;
               sprintf (temp, "%f", *(double *) optionsTable[o].arg);
               p = temp + strlen (temp) - 1;
               while (*p == '0')
                  *p-- = 0;
               p = strchr (temp, '.');
               if (*p)
                  *p++ = 0;
               printf ("-%s%c%s", temp, optionsTable[o].shortName, p);
               break;
            case POPT_ARG_STRING:
               if (!*(char **) optionsTable[o].arg)
                  break;
               {
                  char *p = strdupa (*(char * *) optionsTable[o].arg),
                     *q;
                  for (q = p; *q; q++)
                     if (*q <= ' ' || *q == '/' || *q == '\\' || *q == '"' || *q == '\'' || *q == ':' || *q == ';')
                        *q = '_';
                  *q = 0;
                  printf ("-%c%s", optionsTable[o].shortName, p);
               }
               break;
            }
      printf (".%s\r\n\r\n", stl ? "stl" : "scad");     // Used from apache
      fflush (stdout);
   }

   FILE *out = stdout;
   char tmp[] = "/tmp/XXXXXX.scad";
   if (stl)
   {
      int o = mkstemps (tmp, 5);
      if (o < 0)
         err (1, "Cannot make temp");
      out = fdopen (o, "w");
   } else if (outfile && !(out = fopen (outfile, "w")))
      err (1, "Cannot open %s", outfile);

   fprintf (out, "// Puzzlebox by RevK, @TheRealRevK www.me.uk\n");
   fprintf (out, "// Thingiverse examples and instructions https://www.thingiverse.com/thing:2410748\n");
   fprintf (out, "// GitHub source https://github.com/revk/PuzzleBox\n");
   fprintf (out, "// Get new random custom maze gift boxes from https://www.me.uk/puzzlebox\n");
   {                            // Document args
      time_t now = time (0);
      struct tm t;
      gmtime_r (&now, &t);
      fprintf (out, "// Created %04d-%02d-%02dT%02d:%02d:%02dZ %s\n", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour,
               t.tm_min, t.tm_sec, getenv ("REMOTE_ADDR") ? : "");
      int o;
      for (o = 0; optionsTable[o].longName; o++)
         if (optionsTable[o].shortName && optionsTable[o].arg)
            switch (optionsTable[o].argInfo & POPT_ARG_MASK)
            {
            case POPT_ARG_NONE:
               if (*(int *) optionsTable[o].arg)
                  fprintf (out, "// %s: %c\n", optionsTable[o].descrip, optionsTable[o].shortName);
               break;
            case POPT_ARG_INT:
               {
                  int v = *(int *) optionsTable[o].arg;
                  if (v)
                     fprintf (out, "// %s: %c=%d\n", optionsTable[o].descrip, optionsTable[o].shortName, v);
               }
               break;
            case POPT_ARG_DOUBLE:
               {
                  double v = *(double *) optionsTable[o].arg;
                  if (v)
                  {
                     char temp[50],
                      *p;
                     sprintf (temp, "%f", v);
                     for (p = temp + strlen (temp); p > temp && p[-1] == '0'; p--);
                     if (p > temp && p[-1] == '.')
                        p--;
                     *p = 0;
                     fprintf (out, "// %s: %c=%s\n", optionsTable[o].descrip, optionsTable[o].shortName, temp);
                  }
               }
               break;
            case POPT_ARG_STRING:
               {
                  char *v = *(char * *) optionsTable[o].arg;
                  if (v && *v)
                     fprintf (out, "// %s: %c=%s\n", optionsTable[o].descrip, optionsTable[o].shortName, v);
               }
               break;
            }
   }
   if (error)
   {                            // Problem
      fprintf (out, "// ** %s **\n", error);
      return 1;
   }

   // Other adjustments
   basethickness += logodepth;

   {                            // Modules
      if (textslow)
         fprintf
            (out,
             "module cuttext(){translate([0,0,-%d])minkowski(){rotate([0,0,22.5])cylinder(h=%lld,d1=%lld,d2=0,$fn=8);linear_extrude(height=%d,convexity=10)mirror([1,0,0])children();}}\n",
             SCALE, scaled (textdepth), scaled (textdepth), SCALE);
      else
         fprintf (out, "module cuttext(){linear_extrude(height=%lld,convexity=10,center=true)mirror([1,0,0])children();}\n",
                  scaled (textdepth));
      if (ajklogo)
         fprintf (out, "module logo(w=100,$fn=120){scale(w/25)translate([0,0,0.5]){ hull(){translate([-10,-7])sphere(0.5);translate([0,7])sphere(0.5);} hull(){translate([0,7])sphere(0.5);translate([0,-7])sphere(0.5);} hull(){translate([0,0])sphere(0.5);translate([6,7])sphere(0.5);} hull(){translate([0,0])sphere(0.5);translate([6,-7])sphere(0.5);} hull(){translate([0,0])sphere(0.5);translate([-5,0])sphere(0.5);} translate([-2.5,-7])rotate_extrude(angle=180,start=180)translate([2.5,0])rotate(180/$fn)circle(0.5); translate([-5,-7])sphere(0.5); translate([0,-7])sphere(0.5);}}");   // You can use the AJK logo on your maze print providing it is not for sale, and tasteful.
      else if (aalogo)          // You can use the A&A logo on your maze print providing it is no for sale, and tasteful and not in any way derogatory to A&A or any staff/officers.
         fprintf
            (out,
             "module logo(w=100,white=0,$fn=100){scale(w/100){if(!white)difference(){circle(d=100.5);circle(d=99.5);}difference(){if(white)circle(d=100);difference(){circle(d=92);for(m=[0,1])mirror([m,0,0]){difference(){translate([24,0,0])circle(r=22.5);translate([24,0,0])circle(r=15);}polygon([[1.5,22],[9,22],[9,-18.5],[1.5,-22]]);}}}}} // A&A Logo is copyright (c) 2013 and trademark Andrews & Arnold Ltd\n");
   }
   /**
    * Appends formatted string to the maze data buffer for later inclusion in STL comments.
    * Dynamically grows the buffer as needed.
    */
   void appendmazedata (const char *fmt, ...)
   {
      va_list ap;
      va_start (ap, fmt);
      size_t needed = vsnprintf (NULL, 0, fmt, ap) + 1;
      va_end (ap);
      
      if (mazedatasize + needed > mazedatacap)
      {
         mazedatacap = mazedatasize + needed + 4096;
         mazedata = realloc (mazedata, mazedatacap);
         if (!mazedata)
            err (1, "Failed to allocate maze data buffer");
      }
      
      va_start (ap, fmt);
      vsnprintf (mazedata + mazedatasize, needed, fmt, ap);
      va_end (ap);
      mazedatasize += needed - 1;
   }
   /**
    * Generates OpenSCAD code to render text on the puzzle box.
    * Handles text sizing, positioning, font selection, and emoji support.
    * 
    * @param s Text size/scale
    * @param t Text string to render
    * @param f Font name (optional, can be NULL)
    * @param outset If true, text is raised; if false, text is embossed
    */
   void cuttext (double s, char *t, char *f, int outset)
   {
      if (outset)
         fprintf (out, "mirror([0,0,1])");
      fprintf (out, "cuttext()");
      fprintf (out, "scale(%lld)", scaled (1));
      fprintf (out, "text(\"%s\"", t);
      fprintf (out, ",halign=\"center\"");
      fprintf (out, ",valign=\"center\"");
      fprintf (out, ",size=%lf", s);
      if (*t & 0x80)
         fprintf (out, ",font=\"Noto Emoji\""); // Assume emoji - not clean - TODO needs fontconfig stuff really
      else if (f)
         fprintf (out, ",font=\"%s\"", f);
      fprintf (out, ");\n");
   }
   // The base
   fprintf (out, "module outer(h,r){e=%lld;minkowski(){cylinder(r1=0,r2=e,h=e,$fn=24);cylinder(h=h-e,r=r,$fn=%d);}}\n",
            scaled (outerround), outersides ? : 100);
   // Start
   double x = 0,
      y = 0;
   int sq = sqrt (parts) + 0.5,
      n = sq * sq - parts;
   /**
    * Generates OpenSCAD code for a single part of the puzzle box.
    * Creates the cylindrical structure, maze patterns, nubs, text, and logos.
    * Handles both inside and outside maze configurations.
    * 
    * @param part Part number to generate (1-based indexing)
    * @return 0 on success
    */
   int box (int part)
   {                            // Make the box - part 1 in inside
      int N,
        X,
        Y,
        Z,
        S;
      double entrya = 0;        // Entry angle
      double mazeexit = 0;      // Maze exit angle (saved for opposite nub positioning)
      int mazeinside = inside;  // This part has maze inside
      int mazeoutside = !inside;        // This part has maze outside
      int nextinside = inside;  // Next part has maze inside
      int nextoutside = !inside;        // Next part has maze outside
      if (flip)
      {
         if (part & 1)
         {
            mazeinside = 1 - mazeinside;
            nextoutside = 1 - nextoutside;
         } else
         {
            mazeoutside = 1 - mazeoutside;
            nextinside = 1 - nextinside;
         }
      }
      if (part == 1)
         mazeinside = 0;
      if (part == parts)
         mazeoutside = 0;
      if (part + 1 >= parts)
         nextoutside = 0;
      if (part == parts)
         nextinside = 0;
      // Dimensions
      // r0 is inside of part+maze
      // r1 is outside of part+maze
      // r2 is outside of base before "sides" adjust
      // r3 is outside of base with "sides" adjust
      double r1 = corediameter / 2 + wallthickness + (part - 1) * (wallthickness + mazethickness + clearance);  // Outer
      if (coresolid)
         r1 -= wallthickness + mazethickness + clearance - (inside ? mazethickness : 0);        // Adjust to make part 2 the core diameter
      int W = ((int) (r1 * 2 * M_PI / mazestep)) / nubs * nubs; // Default value
      double r0 = r1 - wallthickness;   // Inner
      if (mazeinside && part > 1)
         r0 -= mazethickness;   // Maze on inside
      if (mazeoutside && part < parts)
         r1 += mazethickness;   // Maze on outside
      double r2 = r1;           // Base outer
      if (part < parts)
         r2 += clearance;
      if (part + 1 >= parts && textsides && !textoutset)
         r2 += textdepth;
      if (nextinside)
         r2 += mazethickness;
      if (nextoutside || part + 1 == parts)
         r2 += wallthickness;
      if (basewide && part + 1 < parts)
         r2 += nextoutside ? mazethickness : wallthickness;
      double r3 = r2;
      if (outersides && part + 1 >= parts)
         r3 /= cos ((double) M_PI / outersides);        // Bigger because of number of sides
      fprintf (out, "// Part %d (%.2fmm to %.2fmm and %.2fmm/%.2fmm base)\n", part, r0, r1, r2, r3);
      double height = (coresolid ? coregap + baseheight : 0) + coreheight + basethickness + (basethickness + basegap) * (part - 1);
      if (part == 1)
         height -= (coresolid ? coreheight : coregap);
      if (part > 1)
         height -= baseheight;  // base from previous unit is added to this
      // Output
      /**
       * Generates a cylindrical maze pattern on the inside or outside of a part.
       * Creates a random maze using recursive backtracking algorithm, applies helix
       * transformation, and outputs OpenSCAD polyhedron geometry.
       * 
       * @param r Radius at which to generate the maze
       * @param inside If 1, maze is on inside surface; if 0, maze is on outside surface
       */
      void makemaze (double r, int inside)
      {                         // Make the maze
         W = ((int) ((r + (inside ? mazethickness : -mazethickness)) * 2 * M_PI / mazestep)) / nubs * nubs;     // Update W for actual maze
         double base = (inside ? basethickness : baseheight);
         if (inside && part > 2)
            base += baseheight; // Nubs don' t go all the way to the end if (inside && part == 2)
         base += (coresolid ? coreheight : 0);  // First one is short...
         if (inside)
            base += basegap;
         double h = height - base - mazemargin - (parkvertical ? mazestep / 4 : 0) - mazestep / 8;
         int H = (int) (h / mazestep);
         fprintf (out, "// Maze %s %d/%d\n", inside ? "inside" : "outside", W, H);
         double y0 = base + mazestep / 2 - mazestep * (helix + 1) + mazestep / 8;
         H += 2 + helix;        // Allow one above, one below and helix below
         if (W < 3 || H < 1)
            errx (1, "Too small");
         double a = 0,
            dy = 0;
         if (helix)
         {
            a = atan (mazestep * helix / r / 2 / M_PI) * 180 / M_PI;
            dy = mazestep * helix / W;
         }
         unsigned char maze[W][H];
         memset (maze, 0, sizeof (unsigned char) * W * H);
         /**
          * Tests if a maze cell is already in use or out of bounds.
          * Handles wrapping around the X axis (cylindrical topology) and
          * checking the FLAGI (invalid) flag.
          * 
          * @param x X coordinate (wraps around cylinder)
          * @param y Y coordinate (height)
          * @return 1 if cell is in use or invalid, 0 if available
          */
         int test (int x, int y)
         {                      // Test if in use...
            while (x < 0)
            {
               x += W;
               y -= helix;
            }
            while (x >= W)
            {
               x -= W;
               y += helix;
            }
            int n = nubs;
            unsigned char v = 0;
            while (n--)
            {
               if (y < 0 || y >= H)
                  v |= FLAGI;
               else
                  v |= maze[x][y];
               if (!n)
                  break;
               x += W / nubs;
               while (x >= W)
               {
                  x -= W;
                  y += helix;
               }
               if (helix == nubs)
                  y--;
            }
            return v;
         }
         {                      // Maze
            double margin = mazemargin;
            // Make maze
            // Clear too high/low
            for (Y = 0; Y < H; Y++)
               for (X = 0; X < W; X++)
                  if (mazestep * Y + y0 + dy * X < base + mazestep / 2 + mazestep / 8
                      || mazestep * Y + y0 + dy * X > height - mazestep / 2 - margin - mazestep / 8)
                     maze[X][Y] |= FLAGI;       // To high or low
            // Final park point
            if (parkvertical)
            {
               for (N = 0; N < helix + 2; N++)  // Down to final
               {
                  maze[0][N] |= FLAGU + FLAGD;
                  maze[X = 0][Y = N + 1] |= FLAGD;
               }
               if (!inside && !noa && W / nubs > 2 && H > helix + 4)
               {                // An "A" at finish
                  maze[X][Y] |= FLAGD | FLAGU | FLAGR;
                  maze[X][Y + 1] |= FLAGD | FLAGR;
                  maze[X + 1][Y] |= FLAGD | FLAGU | FLAGL;
                  maze[X + 1][Y + 1] |= FLAGD | FLAGL;
                  maze[X + 1][Y - 1] |= FLAGU;
                  X++;
                  Y--;
               }
            } else              // Left to final
            {
               maze[0][helix + 1] |= FLAGR;
               maze[X = 1][Y = helix + 1] |= FLAGL;
               if (!inside && !noa && W / nubs > 3 && H > helix + 3)
               {                // An "A" at finish
                  maze[X][Y] |= FLAGL | FLAGR | FLAGU;
                  maze[X + 1][Y] |= FLAGL | FLAGU;
                  maze[X + 1][Y + 1] |= FLAGL | FLAGD;
                  maze[X][Y + 1] |= FLAGL | FLAGR | FLAGD;
                  maze[X - 1][Y + 1] |= FLAGR;
                  X--;
                  Y++;
               }
            }
            // Make maze
            int maxx = 0;
            if (testmaze)
            {                   // Simple test pattern
               for (Y = 0; Y < H; Y++)
                  for (X = 0; X < W; X++)
                     if (!(test (X, Y) & FLAGI) && !(test (X + 1, Y) & FLAGI))
                     {
                        maze[X][Y] |= FLAGR;
                        int x = X + 1,
                           y = Y;
                        if (x >= W)
                        {
                           x -= W;
                           y += helix;
                        }
                        maze[x][y] |= FLAGL;
                     }
               if (!flip || inside)
                  while (maxx + 1 < W && !(test (maxx + 1, H - 2) & FLAGI))
                     maxx++;
            } else
            {                   // Actual maze
               int max = 0;
               typedef struct pos_s pos_t;
               struct pos_s
               {
                  pos_t *next;
                  int x,
                    y,
                    n;
               };
               pos_t *pos = malloc (sizeof (*pos)),
                  *last = NULL;
               pos->x = X;
               pos->y = Y;
               pos->n = 0;
               pos->next = NULL;
               last = pos;
               while (pos)
               {
                  pos_t *p = pos;
                  pos = p->next;
                  p->next = NULL;
                  if (!pos)
                     last = NULL;
                  // Where we are
                  X = p->x;
                  Y = p->y;
                  int v,
                    n = 0;
                  // Which way can we go
                  // Some bias for direction
                  if (!test (X + 1, Y))
                     n += BIASR;        // Right
                  if (!test (X - 1, Y))
                     n += BIASL;        // Left
                  if (!test (X, Y - 1))
                     n += BIASD;        // Down
                  if (!test (X, Y + 1))
                     n += BIASU;        // Up
                  if (!n)
                  {             // No way forward
                     free (p);
                     continue;
                  }
                  // Pick one of the ways randomly
                  if (read (f, &v, sizeof (v)) != sizeof (v))
                     err (1, "Read /dev/random");
                  v %= n;
                  // Move forward
                  if (!test (X + 1, Y) && (v -= BIASR) < 0)
                  {             // Right
                     maze[X][Y] |= FLAGR;
                     X++;
                     if (X >= W)
                     {
                        X -= W;
                        Y += helix;
                     }
                     maze[X][Y] |= FLAGL;
                  } else if (!test (X - 1, Y) && (v -= BIASL) < 0)
                  {             // Left
                     maze[X][Y] |= FLAGL;
                     X--;
                     if (X < 0)
                     {
                        X += W;
                        Y -= helix;
                     }
                     maze[X][Y] |= FLAGR;
                  } else if (!test (X, Y - 1) && (v -= BIASD) < 0)
                  {             // Down
                     maze[X][Y] |= FLAGD;
                     Y--;
                     maze[X][Y] |= FLAGU;
                  } else if (!test (X, Y + 1) && (v -= BIASU) < 0)
                  {             // Up
                     maze[X][Y] |= FLAGU;
                     Y++;
                     maze[X][Y] |= FLAGD;
                  } else
                     errx (1, "WTF");   // We should have picked a way we can go
                  // Entry
                  if (p->n > max && (test (X, Y + 1) & FLAGI)   //
                      && (!flip || inside || !(X % (W / nubs))))
                  {             // Longest path that reaches top
                     max = p->n;
                     maxx = X;
                  }
                  // Next point to consider
                  pos_t *next = malloc (sizeof (*next));
                  next->x = X;
                  next->y = Y;
                  next->n = p->n + 1;
                  next->next = NULL;
                  // How to add points to queue... start or end
                  if (read (f, &v, sizeof (v)) != sizeof (v))
                     err (1, "Read /dev/random");
                  v %= 10;
                  if (v < (mazecomplexity < 0 ? -mazecomplexity : mazecomplexity))
                  {             // add next point at start - makes for longer path
                     if (!pos)
                        last = next;
                     next->next = pos;
                     pos = next;
                  } else
                  {             // add next point at end - makes for multiple paths, which can mean very simple solution
                     if (last)
                        last->next = next;
                     else
                        pos = next;
                     last = next;
                  }
                  if (mazecomplexity <= 0 && v < -mazecomplexity)
                  {             // current point to start
                     if (!pos)
                        last = p;
                     p->next = pos;
                     pos = p;
                  } else
                  {
                     if (last)
                        last->next = p;
                     else
                        pos = p;
                     last = p;
                  }
               }
               fprintf (out, "// Path length %d\n", max);
            }
            entrya = (double) 360 *maxx / W;
            mazeexit = entrya;  // Save maze exit angle for opposite nub positioning
            if (fixnubs && globalexit == 0)
               globalexit = entrya;  // Save first maze exit globally for consistent nub positioning
            // Entry point for maze
            for (X = maxx % (W / nubs); X < W; X += W / nubs)
            {
               Y = H - 1;
               while (Y && (maze[X][Y] & FLAGI))
                  maze[X][Y--] |= FLAGU + FLAGD;
               maze[X][Y] += FLAGU;
            }

            // Output maze visualization
            fprintf (out, "//\n");
            fprintf (out, "// ============ MAZE VISUALIZATION (%s, %dx%d) ============\n", inside ? "INSIDE" : "OUTSIDE", W, H);
            fprintf (out, "//\n");
            fprintf (out, "// Human-readable maze (viewed from outside, unwrapped):\n");
            fprintf (out, "// Legend: + = corner, - = horizontal wall, | = vertical wall, # = invalid, E = exit, space = passage\n");
            fprintf (out, "// Note: Maze wraps horizontally (cylinder) - leftmost and rightmost edges connect\n");
            fprintf (out, "// Note: With %d nubs, the maze pattern repeats every %d cells around the circumference\n", nubs, W / nubs);
            fprintf (out, "//\n");
            
            // Store in buffer for STL
            if (stl)
            {
               appendmazedata ("\n");
               appendmazedata ("============ MAZE VISUALIZATION (%s, %dx%d) ============\n", inside ? "INSIDE" : "OUTSIDE", W, H);
               appendmazedata ("\n");
               appendmazedata ("Human-readable maze (viewed from outside, unwrapped):\n");
               appendmazedata ("Legend: + = corner, - = horizontal wall, | = vertical wall, # = invalid, E = exit, space = passage\n");
               appendmazedata ("Note: Maze wraps horizontally (cylinder) - leftmost and rightmost edges connect\n");
               appendmazedata ("Note: With %d nubs, the maze pattern repeats every %d cells around the circumference\n", nubs, W / nubs);
               appendmazedata ("\n");
            }
            
            // Human-readable ASCII visualization with walls
            // First, determine the valid row range (skip rows that are all invalid)
            int minY = 0, maxY = H - 1;
            for (Y = 0; Y < H; Y++)
            {
               int all_invalid = 1;
               for (X = 0; X < W; X++)
               {
                  if (!(maze[X][Y] & FLAGI))
                  {
                     all_invalid = 0;
                     break;
                  }
               }
               if (!all_invalid)
               {
                  minY = Y;
                  break;
               }
            }
            for (Y = H - 1; Y >= 0; Y--)
            {
               int all_invalid = 1;
               for (X = 0; X < W; X++)
               {
                  if (!(maze[X][Y] & FLAGI))
                  {
                     all_invalid = 0;
                     break;
                  }
               }
               if (!all_invalid)
               {
                  maxY = Y;
                  break;
               }
            }
            
            fprintf (out, "// Showing rows %d to %d (valid maze area)\n", minY, maxY);
            if (stl)
               appendmazedata ("Showing rows %d to %d (valid maze area)\n", minY, maxY);
            
            // Create a copy of maze data for visualization
            unsigned char maze_viz[W][H];
	    memcpy(maze_viz, maze, sizeof(unsigned char)*W*H);
            
            // Replicate maze data by traversing from start and copying each cell to opposite side
            if (nubs > 1)
            {
               // Use a simple queue for BFS traversal
               int queueX[W * H], queueY[W * H];
               int qhead = 0, qtail = 0;
               char visited[W][H];
               memset(visited, 0, sizeof(visited));
               
               // Start at the entry point
               queueX[qtail] = maxx;
               queueY[qtail] = maxY;
               qtail++;
               visited[maxx][maxY] = 1;
               
               // Copy start cell to opposite side (rotate around Z axis only)
               int opp_x = (maxx + W / nubs) % W;
               int opp_y = maxY;  // Same Y position, no helix offset
               maze_viz[opp_x][opp_y] = maze_viz[maxx][maxY];  // Copy maze data from current cell to opposite side
               
               while (qhead < qtail)
               {
                  int cx = queueX[qhead];
                  int cy = queueY[qhead];
                  qhead++;
                  
                  // Check all four directions
                  // Right
                  if (maze[cx][cy] & FLAGR)
                  {
                     int nx = (cx + 1) % W;
                     int ny = cy;
                     if (!visited[nx][ny])
                     {
                        visited[nx][ny] = 1;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                        // Copy to opposite side (rotate around Z axis only)
                        int opp_x = (nx + W / nubs) % W;
                        int opp_y = ny;  // Same Y position, no helix offset
                        maze_viz[opp_x][opp_y] = maze_viz[nx][ny];  // Copy maze data from current cell to opposite side
                     }
                  }
                  // Left
                  if (maze[cx][cy] & FLAGL)
                  {
                     int nx = (cx - 1 + W) % W;
                     int ny = cy;
                     if (!visited[nx][ny])
                     {
                        visited[nx][ny] = 1;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                        // Copy to opposite side (rotate around Z axis only)
                        int opp_x = (nx + W / nubs) % W;
                        int opp_y = ny;  // Same Y position, no helix offset
                        maze_viz[opp_x][opp_y] = maze_viz[nx][ny];  // Copy maze data from current cell to opposite side
                     }
                  }
                  // Up
                  if (maze[cx][cy] & FLAGU)
                  {
                     int nx = cx;
                     int ny = (cy + 1) % H;
                     if (!visited[nx][ny])
                     {
                        visited[nx][ny] = 1;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                        // Copy to opposite side (rotate around Z axis only)
                        int opp_x = (nx + W / nubs) % W;
                        int opp_y = ny;  // Same Y position, no helix offset
                        maze_viz[opp_x][opp_y] = maze_viz[nx][ny];  // Copy maze data from current cell to opposite side
                     }
                  }
                  // Down
                  if (maze[cx][cy] & FLAGD)
                  {
                     int nx = cx;
                     int ny = (cy - 1 + H) % H;
                     if (!visited[nx][ny])
                     {
                        visited[nx][ny] = 1;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                        // Copy to opposite side (rotate around Z axis only)
                        int opp_x = (nx + W / nubs) % W;
                        int opp_y = ny;  // Same Y position, no helix offset
                        maze_viz[opp_x][opp_y] = maze_viz[nx][ny];  // Copy maze data from current cell to opposite side
                     }
                  }
               }
            }
            
            // Find solution path from entrance to exit
            char solution[W][H];  // Stores direction: 0=none, 'U'=up, 'D'=down, 'L'=left, 'R'=right, 'S'=start
            char reachable[W][H]; // Stores which cells are reachable from entrance
            memset(solution, 0, sizeof(solution));
            memset(reachable, 0, sizeof(reachable));
            
            // Find entrance at bottom (minY) - look for cell with passage down
            int entrance_x = -1;
            for (X = 0; X < W / nubs; X++)  // Only search first sector
            {
               if (!(maze[X][minY] & FLAGI))
               {
                  entrance_x = X;
                  break;
               }
            }
            
            if (entrance_x >= 0)
            {
               // BFS to find path from entrance to exit
               int queueX[W * H], queueY[W * H];
               int parentX[W][H], parentY[W][H];
               int qhead = 0, qtail = 0;
               char visited[W][H];
               memset(visited, 0, sizeof(visited));
               memset(parentX, -1, sizeof(parentX));
               memset(parentY, -1, sizeof(parentY));
               
               queueX[qtail] = entrance_x;
               queueY[qtail] = minY;
               qtail++;
               visited[entrance_x][minY] = 1;
               parentX[entrance_x][minY] = entrance_x;
               parentY[entrance_x][minY] = minY;
               
               int found = 0;
               while (qhead < qtail && !found)
               {
                  int cx = queueX[qhead];
                  int cy = queueY[qhead];
                  qhead++;
                  
                  if (cx == maxx && cy == maxY)
                  {
                     found = 1;
                     break;
                  }
                  
                  // Try all four directions
                  if (maze[cx][cy] & FLAGR)
                  {
                     int nx = cx + 1;
                     int ny = cy;
                     if (nx >= W)
                     {
                        nx -= W;
                        ny += helix;
                     }
                     if (ny >= 0 && ny < H && !visited[nx][ny] && !(maze[nx][ny] & FLAGI))
                     {
                        visited[nx][ny] = 1;
                        parentX[nx][ny] = cx;
                        parentY[nx][ny] = cy;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                     }
                  }
                  if (maze[cx][cy] & FLAGL)
                  {
                     int nx = cx - 1;
                     int ny = cy;
                     if (nx < 0)
                     {
                        nx += W;
                        ny -= helix;
                     }
                     if (ny >= 0 && ny < H && !visited[nx][ny] && !(maze[nx][ny] & FLAGI))
                     {
                        visited[nx][ny] = 1;
                        parentX[nx][ny] = cx;
                        parentY[nx][ny] = cy;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                     }
                  }
                  if (maze[cx][cy] & FLAGU)
                  {
                     int nx = cx;
                     int ny = (cy + 1) % H;
                     if (!visited[nx][ny] && !(maze[nx][ny] & FLAGI))
                     {
                        visited[nx][ny] = 1;
                        parentX[nx][ny] = cx;
                        parentY[nx][ny] = cy;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                     }
                  }
                  if (maze[cx][cy] & FLAGD)
                  {
                     int nx = cx;
                     int ny = (cy - 1 + H) % H;
                     if (!visited[nx][ny] && !(maze[nx][ny] & FLAGI))
                     {
                        visited[nx][ny] = 1;
                        parentX[nx][ny] = cx;
                        parentY[nx][ny] = cy;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                     }
                  }
               }
               
               // Trace back from exit to entrance to mark solution path
               if (found)
               {
                  // Build path from entrance to exit by following parents backward
                  int path_x[W * H], path_y[W * H];
                  int path_len = 0;
                  
                  int cx = maxx;
                  int cy = maxY;
                  
                  // Trace back to build path array
                  while (1)
                  {
                     path_x[path_len] = cx;
                     path_y[path_len] = cy;
                     path_len++;
                     
                     if (cx == entrance_x && cy == minY)
                        break;
                     
                     int px = parentX[cx][cy];
                     int py = parentY[cx][cy];
                     cx = px;
                     cy = py;
                  }
                  
                  // Now mark cells with arrows pointing toward exit
                  // path[path_len-1] is entrance, path[0] is exit
                  solution[path_x[path_len-1]][path_y[path_len-1]] = 'S';  // Mark start
                  
                  // Mark each cell on the path with arrow pointing toward exit
                  for (int i = path_len - 2; i > 0; i--)
                  {
                     int curr_x = path_x[i];
                     int curr_y = path_y[i];
                     int next_x = path_x[i-1];  // Cell closer to exit
                     int next_y = path_y[i-1];
                     
                     // Determine direction from current to next (toward exit)
                     // Handle helix wrapping - movement can be diagonal when wrapping
                     int dx = (next_x - curr_x + W) % W;
                     int dy = next_y - curr_y;
                     
                     // Determine primary direction
                     if (dx == 0 && dy != 0)
                     {
                        // Pure vertical movement
                        if (dy > 0)
                           solution[curr_x][curr_y] = 'U';
                        else
                           solution[curr_x][curr_y] = 'D';
                     }
                     else if (dy == 0 && dx != 0)
                     {
                        // Pure horizontal movement
                        if (dx == 1)
                           solution[curr_x][curr_y] = 'R';
                        else if (dx == W - 1)
                           solution[curr_x][curr_y] = 'L';
                        else
                           solution[curr_x][curr_y] = '?';  // Shouldn't happen
                     }
                     else if (dx != 0 && dy != 0)
                     {
                        // Diagonal movement (due to helix wrapping)
                        // Choose primary direction based on which is more significant
                        if (dx == 1 || dx == W - 1)
                        {
                           // Horizontal wrap with vertical adjustment
                           if (dx == 1)
                              solution[curr_x][curr_y] = 'R';
                           else
                              solution[curr_x][curr_y] = 'L';
                        }
                        else
                        {
                           // Shouldn't happen - use vertical
                           if (dy > 0)
                              solution[curr_x][curr_y] = 'U';
                           else
                              solution[curr_x][curr_y] = 'D';
                        }
                     }
                     else
                     {
                        // No movement? Shouldn't happen
                        solution[curr_x][curr_y] = '?';
                     }
                  }
                  
                  // Mark exit cell (path[0]) - it leads up and out
                  solution[path_x[0]][path_y[0]] = 'U';
               }
               
               // Now mark all cells reachable from entrance (for dead end detection)
               // Reuse the BFS queue
               qhead = 0;
               qtail = 0;
               
               queueX[qtail] = entrance_x;
               queueY[qtail] = minY;
               qtail++;
               reachable[entrance_x][minY] = 1;
               
               while (qhead < qtail)
               {
                  int cx = queueX[qhead];
                  int cy = queueY[qhead];
                  qhead++;
                  
                  // Try all four directions
                  if (maze[cx][cy] & FLAGR)
                  {
                     int nx = cx + 1;
                     int ny = cy;
                     if (nx >= W)
                     {
                        nx -= W;
                        ny += helix;
                     }
                     if (ny >= 0 && ny < H && !reachable[nx][ny] && !(maze[nx][ny] & FLAGI))
                     {
                        reachable[nx][ny] = 1;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                     }
                  }
                  if (maze[cx][cy] & FLAGL)
                  {
                     int nx = cx - 1;
                     int ny = cy;
                     if (nx < 0)
                     {
                        nx += W;
                        ny -= helix;
                     }
                     if (ny >= 0 && ny < H && !reachable[nx][ny] && !(maze[nx][ny] & FLAGI))
                     {
                        reachable[nx][ny] = 1;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                     }
                  }
                  if (maze[cx][cy] & FLAGU)
                  {
                     int nx = cx;
                     int ny = cy + 1;
                     if (ny >= 0 && ny < H && !reachable[nx][ny] && !(maze[nx][ny] & FLAGI))
                     {
                        reachable[nx][ny] = 1;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                     }
                  }
                  if (maze[cx][cy] & FLAGD)
                  {
                     int nx = cx;
                     int ny = cy - 1;
                     if (ny >= 0 && ny < H && !reachable[nx][ny] && !(maze[nx][ny] & FLAGI))
                     {
                        reachable[nx][ny] = 1;
                        queueX[qtail] = nx;
                        queueY[qtail] = ny;
                        qtail++;
                     }
                  }
               }
            }
            
            for (Y = maxY + 1; Y >= minY; Y--)
            {
               // Draw horizontal walls and corners
               fprintf (out, "// ");
               if (stl)
                  appendmazedata (" ");
               for (X = 0; X < W; X++)
               {
                  fprintf (out, "+");
                  if (stl)
                     appendmazedata ("+");
                  // Draw horizontal edge between cells
                  if (Y == maxY + 1)
                  {
                     // Top border - check if this is an exit (exits occur at multiples of W/nubs)
                     int is_exit = 0;
                     for (int n = 0; n < nubs; n++)
                     {
                        int exit_x = (maxx + n * (W / nubs)) % W;
                        if (X == exit_x)
                        {
                           is_exit = 1;
                           break;
                        }
                     }
                     if (is_exit)
                        fprintf (out, " E ");
                     else
                        fprintf (out, "---");
                     if (stl)
                     {
                        if (is_exit)
                           appendmazedata (" E ");
                        else
                           appendmazedata ("---");
                     }
                  }
                  else if (Y == minY)
                  {
                     // Bottom border
                     fprintf (out, "---");
                     if (stl)
                        appendmazedata ("---");
                  }
                  else
                  {
                     // Interior - check if there's a passage up from cell below
                     if ((maze_viz[X][Y - 1] & FLAGU))
                        fprintf (out, "   ");  // Passage (no wall)
                     else
                        fprintf (out, "---");  // Wall
                     if (stl)
                     {
                        if ((maze_viz[X][Y - 1] & FLAGU))
                           appendmazedata ("   ");
                        else
                           appendmazedata ("---");
                     }
                  }
               }
               fprintf (out, "+\n");
               if (stl)
                  appendmazedata ("+\n");
               
               // Draw vertical walls and cell interiors
               if (Y > minY)
               {
                  fprintf (out, "// ");
                  if (stl)
                     appendmazedata (" ");
                  
                  for (X = 0; X < W; X++)
                  {
                     // Left edge - check for wrap-around from previous cell
                     if (X == 0)
                     {
                        // Check if last cell (W-1) has FLAGR (connects to cell 0)
                        if (maze_viz[W - 1][Y - 1] & FLAGR)
                        {
                           fprintf (out, " ");  // Passage wrapping from last to first
                           if (stl)
                              appendmazedata (" ");
                        }
                        else
                        {
                           fprintf (out, "|");  // Wall at left boundary
                           if (stl)
                              appendmazedata ("|");
                        }
                     }
                     
                     // Cell interior
                     if (maze_viz[X][Y - 1] & FLAGI)
                     {
                        fprintf (out, "###");
                        if (stl)
                           appendmazedata ("###");
                     }
                     else
                     {
                        fprintf (out, "   ");
                        if (stl)
                           appendmazedata ("   ");
                     }
                     
                     // Right edge - check if there's a passage to the right
                     if (maze_viz[X][Y - 1] & FLAGR)
                     {
                        fprintf (out, " ");  // Passage to right
                        if (stl)
                           appendmazedata (" ");
                     }
                     else
                     {
                        fprintf (out, "|");  // Wall to right
                        if (stl)
                           appendmazedata ("|");
                     }
                  }
                  fprintf (out, "\n");
                  if (stl)
                     appendmazedata ("\n");
               }
            }
            fprintf (out, "//\n");
            if (stl)
               appendmazedata ("\n");
            
            // Second visualization with solution
            fprintf (out, "//\n");
            fprintf (out, "// ============ MAZE WITH SOLUTION ============\n");
            fprintf (out, "//\n");
            fprintf (out, "// Legend: S = start, arrows (↑↓←→) show path to exit\n");
            fprintf (out, "//\n");
            if (stl)
            {
               appendmazedata ("\n");
               appendmazedata ("============ MAZE WITH SOLUTION ============\n");
               appendmazedata ("\n");
               appendmazedata ("Legend: S = start, arrows (↑↓←→) show path to exit\n");
               appendmazedata ("\n");
            }
            
            for (Y = maxY + 1; Y >= minY; Y--)
            {
               // Draw horizontal walls and corners
               fprintf (out, "// ");
               if (stl)
                  appendmazedata (" ");
               for (X = 0; X < W; X++)
               {
                  fprintf (out, "+");
                  if (stl)
                     appendmazedata ("+");
                  // Draw horizontal edge between cells
                  if (Y == maxY + 1)
                  {
                     // Top border - check if this is an exit (exits occur at multiples of W/nubs)
                     int is_exit = 0;
                     for (int n = 0; n < nubs; n++)
                     {
                        int exit_x = (maxx + n * (W / nubs)) % W;
                        if (X == exit_x)
                        {
                           is_exit = 1;
                           break;
                        }
                     }
                     if (is_exit)
                        fprintf (out, " E ");
                     else
                        fprintf (out, "---");
                     if (stl)
                     {
                        if (is_exit)
                           appendmazedata (" E ");
                        else
                           appendmazedata ("---");
                     }
                  }
                  else if (Y == minY)
                  {
                     // Bottom border
                     fprintf (out, "---");
                     if (stl)
                        appendmazedata ("---");
                  }
                  else
                  {
                     // Interior - check if there's a passage up from cell below
                     if ((maze_viz[X][Y - 1] & FLAGU))
                        fprintf (out, "   ");  // Passage (no wall)
                     else
                        fprintf (out, "---");  // Wall
                     if (stl)
                     {
                        if ((maze_viz[X][Y - 1] & FLAGU))
                           appendmazedata ("   ");
                        else
                           appendmazedata ("---");
                     }
                  }
               }
               fprintf (out, "+\n");
               if (stl)
                  appendmazedata ("+\n");
               
               // Draw vertical walls and cell interiors with solution
               if (Y > minY)
               {
                  fprintf (out, "// ");
                  if (stl)
                     appendmazedata (" ");
                  
                  for (X = 0; X < W; X++)
                  {
                     // Left edge - check for wrap-around from previous cell
                     if (X == 0)
                     {
                        // Check if last cell (W-1) has FLAGR (connects to cell 0)
                        if (maze_viz[W - 1][Y - 1] & FLAGR)
                        {
                           fprintf (out, " ");  // Passage wrapping from last to first
                           if (stl)
                              appendmazedata (" ");
                        }
                        else
                        {
                           fprintf (out, "|");  // Wall at left boundary
                           if (stl)
                              appendmazedata ("|");
                        }
                     }
                     
                     // Cell interior with solution
                     if (maze_viz[X][Y - 1] & FLAGI)
                     {
                        fprintf (out, "###");
                        if (stl)
                           appendmazedata ("###");
                     }
                     else
                     {
                        // Check if this cell is on the solution path
                        char sol = solution[X][Y - 1];
                        if (sol == 'S')
                        {
                           fprintf (out, " S ");
                           if (stl)
                              appendmazedata (" S ");
                        }
                        else if (sol == 'U')
                        {
                           fprintf (out, " ↑ ");
                           if (stl)
                              appendmazedata (" ↑ ");
                        }
                        else if (sol == 'D')
                        {
                           fprintf (out, " ↓ ");
                           if (stl)
                              appendmazedata (" ↓ ");
                        }
                        else if (sol == 'L')
                        {
                           fprintf (out, " ← ");
                           if (stl)
                              appendmazedata (" ← ");
                        }
                        else if (sol == 'R')
                        {
                           fprintf (out, " → ");
                           if (stl)
                              appendmazedata (" → ");
                        }
                        else if (!reachable[X][Y - 1])
                        {
                           // Cell is not reachable from entrance (dead ends, isolated sections)
                           fprintf (out, "###");
                           if (stl)
                              appendmazedata ("###");
                        }
                        else
                        {
                           // Cell is accessible but not on solution (dead ends, traps)
                           fprintf (out, "   ");
                           if (stl)
                              appendmazedata ("   ");
                        }
                     }
                     
                     // Right edge - check if there's a passage to the right
                     if (maze_viz[X][Y - 1] & FLAGR)
                     {
                        fprintf (out, " ");  // Passage to right
                        if (stl)
                           appendmazedata (" ");
                     }
                     else
                     {
                        fprintf (out, "|");  // Wall to right
                        if (stl)
                           appendmazedata ("|");
                     }
                  }
                  fprintf (out, "\n");
                  if (stl)
                     appendmazedata ("\n");
               }
            }
            fprintf (out, "//\n");
            if (stl)
               appendmazedata ("\n");
            
            // Machine-readable format
            fprintf (out, "// Machine-readable maze data:\n");
            fprintf (out, "// MAZE_START %s %d %d %d %d %d %d\n", inside ? "INSIDE" : "OUTSIDE", W, maxY - minY + 1, maxx, helix, minY, maxY);
            if (stl)
            {
               appendmazedata ("Machine-readable maze data:\n");
               appendmazedata ("MAZE_START %s %d %d %d %d %d %d\n", inside ? "INSIDE" : "OUTSIDE", W, maxY - minY + 1, maxx, helix, minY, maxY);
            }
            for (Y = minY; Y <= maxY; Y++)
            {
               fprintf (out, "// MAZE_ROW %d ", Y);
               if (stl)
                  appendmazedata ("MAZE_ROW %d ", Y);
               for (X = 0; X < W; X++)
               {
                  fprintf (out, "%02X", maze_viz[X][Y]);
                  if (stl)
                     appendmazedata ("%02X", maze_viz[X][Y]);
                  if (X < W - 1)
                  {
                     fprintf (out, " ");
                     if (stl)
                        appendmazedata (" ");
                  }
               }
               fprintf (out, "\n");
               if (stl)
                  appendmazedata ("\n");
            }
            fprintf (out, "// MAZE_END\n");
            fprintf (out, "//\n");
            if (stl)
            {
               appendmazedata ("MAZE_END\n");
               appendmazedata ("\n");
            }

            int MAXY = height / (mazestep / 4) + 10;
            struct
            {                   // Data for each slive
               // Pre calculated x/y for left side 0=back, 1=recess, 2=front - used to create points
               double x[3],
                 y[3];
               // The last points as we work up slice (-ve for recess, 0 for not set yet)
               int l,
                 r;
               // Points from bottom up on this slice in order - used to ensure manifold buy using points that would be skipped
               int n;           // Points added to p
               int p[MAXY];
            } s[W * 4];
            memset (&s, 0, sizeof (*s) * W * 4);
            int p[W][H];        // The point start for each usable maze location (0 for not set) - 16 points
            memset (*p, 0, sizeof (int) * W * H);
            // Work out pre-sets
            for (S = 0; S < W * 4; S++)
            {
               double a = M_PI * 2 * (S - 1.5) / W / 4;
               if (!inside)
                  a = M_PI * 2 - a;
               double sa = sin (a),
                  ca = cos (a);
               if (inside)
               {
                  s[S].x[0] = (r + mazethickness + (part < parts ? wallthickness : clearance + 0.01)) * sa;
                  s[S].y[0] = (r + mazethickness + (part < parts ? wallthickness : clearance + 0.01)) * ca;
                  s[S].x[1] = (r + mazethickness) * sa;
                  s[S].y[1] = (r + mazethickness) * ca;
                  s[S].x[2] = r * sa;
                  s[S].y[2] = r * ca;
               } else
               {
                  s[S].x[0] = (r - mazethickness - wallthickness) * sa;
                  s[S].y[0] = (r - mazethickness - wallthickness) * ca;
                  s[S].x[1] = (r - mazethickness) * sa;
                  s[S].y[1] = (r - mazethickness) * ca;
                  s[S].x[2] = r * sa;
                  s[S].y[2] = r * ca;
               }
            }
            if (inside && mirrorinside)
               fprintf (out, "mirror([1,0,0])");
            fprintf (out, "polyhedron(");
            // Make points
            fprintf (out, "points=[");
            int P = 0;
            void addpoint (int S, double x, double y, double z)
            {
               fprintf (out, "[%lld,%lld,%lld],", scaled (x), scaled (y), scaled (z));
               if (s[S].n >= MAXY)
                  errx (1, "WTF points %d", S);
               s[S].p[s[S].n++] = P++;
            }
            void addpointr (int S, double x, double y, double z)
            {
               fprintf (out, "[%lld,%lld,%lld],", scaled (x), scaled (y), scaled (z));
               if (s[S].n >= MAXY)
                  errx (1, "WTF points %d", S);
               s[S].p[s[S].n++] = -(P++);
            }
            int bottom = P;
            // Base points
            for (S = 0; S < W * 4; S++)
               addpoint (S, s[S].x[0], s[S].y[0], basethickness - clearance);
            for (S = 0; S < W * 4; S++)
               addpointr (S, s[S].x[1], s[S].y[1], basethickness - clearance);
            for (S = 0; S < W * 4; S++)
               addpoint (S, s[S].x[2], s[S].y[2], basethickness - clearance);
            {                   // Points for each maze location
               double dy = mazestep * helix / W / 4;    // Step per S
               double my = mazestep / 8;        // Vertical steps
               double y = y0 - dy * 1.5;        // Y vertical centre for S=0
               for (Y = 0; Y < H; Y++)
                  for (X = 0; X < W; X++)
                  {
                     unsigned char v = test (X, Y);
                     if (!(v & FLAGA) || (v & FLAGI))
                        continue;
                     p[X][Y] = P;
                     for (S = X * 4; S < X * 4 + 4; S++)
                        addpoint (S, s[S].x[2], s[S].y[2], y + Y * mazestep + dy * S - my * 3);
                     for (S = X * 4; S < X * 4 + 4; S++)
                        addpointr (S, s[S].x[1], s[S].y[1], y + Y * mazestep + dy * S - my - nubskew);
                     for (S = X * 4; S < X * 4 + 4; S++)
                        addpointr (S, s[S].x[1], s[S].y[1], y + Y * mazestep + dy * S + my - nubskew);
                     for (S = X * 4; S < X * 4 + 4; S++)
                        addpoint (S, s[S].x[2], s[S].y[2], y + Y * mazestep + dy * S + my * 3);
                  }
            }
            int top = P;
            for (S = 0; S < W * 4; S++)
               addpoint (S, s[S].x[2], s[S].y[2], height - (basewide && !inside && part > 1 ? 0 : margin));     // lower
            for (S = 0; S < W * 4; S++)
               addpoint (S, s[S].x[1], s[S].y[1], height);
            for (S = 0; S < W * 4; S++)
               addpoint (S, s[S].x[0], s[S].y[0], height);
            for (S = 0; S < W * 4; S++)
            {                   // Wrap back to start
               if (s[S].n >= MAXY)
                  errx (1, "WTF points");
               s[S].p[s[S].n++] = S;
            }
            fprintf (out, "]");
            // Make faces
            void slice (int S, int l, int r)
            {                   // Advance slice S to new L and R (-ve for recess)
               inline int abs (int x)
               {
                  if (x < 0)
                     return -x;
                  return x;
               }
               inline int sgn (int x)
               {
                  if (x < 0)
                     return -1;
                  if (x > 0)
                     return 1;
                  return 0;
               }
               if (S >= W * 4)
                  errx (1, "Bad render %d", S);
               char start = 0;
               if (!s[S].l)
               {                // New - draw to bottom
                  s[S].l = (l < 0 ? -1 : 1) * (bottom + S + W * 4 + (l < 0 ? 0 : W * 4));
                  s[S].r = (r < 0 ? -1 : 1) * (bottom + (S + 1) % (W * 4) + W * 4 + (r < 0 ? 0 : W * 4));
                  fprintf (out, "[%d,%d,%d,%d],", abs (s[S].l), abs (s[S].r), (S + 1) % (W * 4), S);
               }
               // Advance
               if (l == s[S].l && r == s[S].r)
                  return;
               int SR = (S + 1) % (W * 4);
               fprintf (out, "[");
               int p = 0;
               int n1,
                 n2;
               for (n1 = 0; n1 < s[S].n && abs (s[S].p[n1]) != abs (s[S].l); n1++);
               for (n2 = n1; n2 < s[S].n && abs (s[S].p[n2]) != abs (l); n2++);
               if (n1 == s[S].n || n2 == s[S].n)
                  errx (1, "Bad render %d->%d", s[S].l, l);
               while (n1 < n2)
               {
                  if (sgn (s[S].p[n1]) == sgn (s[S].l))
                  {
                     fprintf (out, "%d,", abs (s[S].p[n1]));
                     p++;
                  }
                  n1++;
               }
               fprintf (out, "%d,", abs (l));
               if (p)
                  fprintf (out, "%d],", abs (r));       // Triangles
               for (n1 = 0; n1 < s[SR].n && abs (s[SR].p[n1]) != abs (s[S].r); n1++);
               for (n2 = n1; n2 < s[SR].n && abs (s[SR].p[n2]) != abs (r); n2++);
               if (n1 == s[SR].n || n2 == s[SR].n)
                  errx (1, "Bad render %d->%d", r, s[S].r);
               if (!p || n1 < n2)
               {
                  n2--;
                  if (p)
                     fprintf (out, "[");
                  fprintf (out, "%d", abs (r));
                  while (n1 <= n2)
                  {
                     if (sgn (s[SR].p[n2]) == sgn (s[S].r))
                        fprintf (out, ",%d", abs (s[SR].p[n2]));
                     n2--;
                  }
                  if (p)
                     fprintf (out, ",%d", abs (s[S].l));
                  fprintf (out, "],");
               }
               s[S].l = l;
               s[S].r = r;
            }
            fprintf (out, ",\nfaces=[");
            // Maze
            for (Y = 0; Y < H; Y++)
               for (X = 0; X < W; X++)
               {
                  unsigned char v = test (X, Y);
                  if (!(v & FLAGA) || (v & FLAGI))
                     continue;
                  S = X * 4;
                  int P = p[X][Y];
                  // Left
                  if (!(v & FLAGD))
                     slice (S + 0, P + 0, P + 1);
                  slice (S + 0, P + 0, -(P + 5));
                  if (v & FLAGL)
                  {
                     slice (S + 0, -(P + 4), -(P + 5));
                     slice (S + 0, -(P + 8), -(P + 9));
                  }
                  slice (S + 0, P + 12, -(P + 9));
                  if (!(v & FLAGU))
                     slice (S + 0, P + 12, P + 13);
                  // Middle
                  if (!(v & FLAGD))
                     slice (S + 1, P + 1, P + 2);
                  slice (S + 1, -(P + 5), -(P + 6));
                  slice (S + 1, -(P + 9), -(P + 10));
                  if (!(v & FLAGU))
                     slice (S + 1, P + 13, P + 14);
                  // Right
                  if (!(v & FLAGD))
                     slice (S + 2, P + 2, P + 3);
                  slice (S + 2, -(P + 6), P + 3);
                  if (v & FLAGR)
                  {
                     slice (S + 2, -(P + 6), -(P + 7));
                     slice (S + 2, -(P + 10), -(P + 11));
                  }
                  slice (S + 2, -(P + 10), P + 15);
                  if (!(v & FLAGU))
                     slice (S + 2, P + 14, P + 15);
                  {             // Joining to right
                     int x = X + 1,
                        y = Y;
                     if (x >= W)
                     {
                        x -= W;
                        y += helix;
                     }
                     if (y >= 0 && y < H)
                     {
                        int PR = p[x][y];
                        if (PR)
                        {
                           slice (S + 3, P + 3, PR + 0);
                           if (v & FLAGR)
                           {
                              slice (S + 3, -(P + 7), -(PR + 4));
                              slice (S + 3, -(P + 11), -(PR + 8));
                           }
                           slice (S + 3, P + 15, PR + 12);
                        }
                     }
                  }
               }
            // Top
            for (S = 0; S < W * 4; S++)
            {
               //slice (S, (s[S].l < 0 ? -1 : 1) * (top + S + (s[S].l < 0 ? W * 4 : 0)), (s[S].r < 0 ? -1 : 1) * (top + ((S + 1) % (W * 4)) + (s[S].r < 0 ? W * 4 : 0)));
               slice (S, top + S + (s[S].l < 0 ? W * 4 : 0), top + ((S + 1) % (W * 4)) + (s[S].r < 0 ? W * 4 : 0));
               slice (S, top + S + W * 4, top + ((S + 1) % (W * 4)) + W * 4);
               slice (S, top + S + 2 * W * 4, top + ((S + 1) % (W * 4)) + 2 * W * 4);
               slice (S, bottom + S, bottom + (S + 1) % (W * 4));
            }
            fprintf (out, "]");
            fprintf (out, ",convexity=10");
            // Done
            fprintf (out, ");\n");
            if (parkthickness)
            {                   // Park ridge
               if (inside && mirrorinside)
                  fprintf (out, "mirror([1,0,0])");
               fprintf (out, "polyhedron(points=[");
               for (N = 0; N < W; N += W / nubs)
                  for (Y = 0; Y < 4; Y++)
                     for (X = 0; X < 4; X++)
                     {
                        int S = N * 4 + X + (parkvertical ? 0 : 2);
                        double z =
                           y0 - dy * 1.5 / 4 + (helix + 1) * mazestep + Y * mazestep / 4 + dy * X / 4 +
                           (parkvertical ? mazestep / 8 : dy / 2 - mazestep * 3 / 8);
                        double x = s[S].x[1];
                        double y = s[S].y[1];
                        if (parkvertical ? Y == 1 || Y == 2 : X == 1 || X == 2)
                        {       // ridge height instead or surface
                           x = (s[S].x[1] * (mazethickness - parkthickness) + s[S].x[2] * parkthickness) / mazethickness;
                           y = (s[S].y[1] * (mazethickness - parkthickness) + s[S].y[2] * parkthickness) / mazethickness;
                        } else if (parkvertical)
                           z -= nubskew;
                        fprintf (out, "[%lld,%lld,%lld],", scaled (s[S].x[0]), scaled (s[S].y[0]), scaled (z));
                        fprintf (out, "[%lld,%lld,%lld],", scaled (x), scaled (y), scaled (z));
                     }
               fprintf (out, "],faces=[");
               for (N = 0; N < nubs; N++)
               {
                  int P = N * 32;
                  inline void add (int a, int b, int c, int d)
                  {
                     fprintf (out, "[%d,%d,%d],[%d,%d,%d],", P + a, P + b, P + c, P + a, P + c, P + d);
                  }
                  for (X = 0; X < 6; X += 2)
                  {
                     add (X + 0, X + 1, X + 3, X + 2);
                     for (Y = 0; Y < 24; Y += 8)
                     {
                        add (X + 0 + Y, X + 2 + Y, X + 10 + Y, X + 8 + Y);
                        add (X + 1 + Y, X + 9 + Y, X + 11 + Y, X + 3 + Y);
                     }
                     add (X + 25, X + 24, X + 26, X + 27);
                  }
                  for (Y = 0; Y < 24; Y += 8)
                  {
                     add (Y + 0, Y + 8, Y + 9, Y + 1);
                     add (Y + 6, Y + 7, Y + 15, Y + 14);
                  }
               }
               fprintf (out, "],convexity=10);\n");
            }
         }
      }

      fprintf (out, "translate([%lld,%lld,0])\n", scaled (x + (outersides & 1 ? r3 : r2)), scaled (y + (outersides & 1 ? r3 : r2)));
      if (outersides)
         fprintf (out, "rotate([0,0,%f])", (double) 180 / outersides + (part + 1 == parts ? 180 : 0));
      fprintf (out, "{\n");
      /**
       * Generates a small alignment mark at position zero on the puzzle box.
       * Used when the number of nubs doesn't evenly divide the number of outer sides,
       * helping with proper rotational alignment during assembly.
       */
      void mark (void)
      {                         // Marking position 0
         if (!markpos0 || part + 1 < parts)
            return;
         double a = 0,
            r = r0 + wallthickness / 2,
            t = wallthickness * 2;
         if (mazeinside)
            r = r0 + mazethickness + wallthickness / 2;
         else if (mazeoutside)
            r = r1 - mazethickness - wallthickness / 2;
         if (!mazeoutside)
         {                      // Try not to cut outside of box
            r -= wallthickness / 2;
            t = wallthickness * 3 / 2;
         }
         if (part == parts && mazeinside)
            a = (mirrorinside ? 1 : -1) * entrya;
         if (part + 1 == parts && mazeoutside)
            a = entrya;
         fprintf (out, "rotate([0,0,%f])translate([0,%lld,%lld])cylinder(d=%lld,h=%lld,center=true,$fn=4);\n", a, scaled (r),
                  scaled (height), scaled (t), scaled (mazestep / 2));
      }

      // Maze
      fprintf (out, "difference(){union(){");
      if (mazeinside)
         makemaze (r0, 1);
      if (mazeoutside)
         makemaze (r1, 0);
      if (!mazeinside && !mazeoutside && part < parts)
      {
         fprintf (out, "difference(){\n");
         fprintf (out, "translate([0,0,%lld])cylinder(r=%lld,h=%lld,$fn=%d);translate([0,0,%lld])cylinder(r=%lld,h=%lld,$fn=%d);\n", scaled (basethickness / 2 - clearance), scaled (r1), scaled (height - basethickness / 2 + clearance), W * 4, scaled (basethickness), scaled (r0), scaled (height), W * 4); // Non maze
         fprintf (out, "}\n");
      }
      // Base
      fprintf (out, "difference(){\n");
      if (part == parts)
         fprintf (out, "outer(%lld,%lld);\n", scaled (height),
                  scaled ((r2 - outerround) / cos ((double) M_PI / (outersides ? : 100))));
      else if (part + 1 >= parts)
         fprintf (out, "mirror([1,0,0])outer(%lld,%lld);\n", scaled (baseheight),
                  scaled ((r2 - outerround) / cos ((double) M_PI / (outersides ? : 100))));
      else
         fprintf (out, "hull(){cylinder(r=%lld,h=%lld,$fn=%d);translate([0,0,%lld])cylinder(r=%lld,h=%lld,$fn=%d);}\n",
                  scaled (r2 - mazethickness), scaled (baseheight), W * 4, scaled (mazemargin), scaled (r2),
                  scaled (baseheight - mazemargin), W * 4);
      fprintf (out, "translate([0,0,%lld])cylinder(r=%lld,h=%lld,$fn=%d);\n", scaled (basethickness), scaled (r0 + (part > 1 && mazeinside ? mazethickness + clearance : 0) + (!mazeinside && part < parts ? clearance : 0)), scaled (height), W * 4);  // Hole
      fprintf (out, "}\n");
      fprintf (out, "}\n");
      if (gripdepth)
      {                         // Cut outs
         if (part + 1 < parts)
            fprintf
               (out,
                "rotate([0,0,%f])translate([0,0,%lld])rotate_extrude(start=180,angle=360,convexity=10,$fn=%d)translate([%lld,0,0])circle(r=%lld,$fn=9);\n",
                (double) 360 / W / 4 / 2, scaled (mazemargin + (baseheight - mazemargin) / 2), W * 4,
                scaled (r2 + gripdepth), scaled (gripdepth * 2));
         else if (part + 1 == parts)
            fprintf (out,
                     "translate([0,0,%lld])rotate_extrude(start=180,angle=360,convexity=10,$fn=%d)translate([%lld,0,0])circle(r=%lld,$fn=9);\n",
                     scaled (outerround + (baseheight - outerround) / 2), outersides ? : 100, scaled (r3 + gripdepth),
                     scaled (gripdepth * 2));
      }
      if (basewide && nextoutside && part + 1 < parts)  // Connect endpoints over base
      {
         int W = ((int) ((r2 - mazethickness) * 2 * M_PI / mazestep)) / nubs * nubs;
         double wi = 2 * (r2 - mazethickness) * 2 * M_PI / W / 4;
         double wo = 2 * r2 * 2 * M_PI * 3 / W / 4;
         fprintf
            (out,
             "for(a=[0:%f:359])rotate([0,0,a])translate([0,%lld,0])hull(){cube([%lld,%lld,%lld],center=true);cube([%lld,0.01,%lld],center=true);}\n",
             (double) 360 / nubs, scaled (r2), scaled (wi), scaled (mazethickness * 2), scaled (baseheight * 2 + clearance),
             scaled (wo), scaled (baseheight * 2 + clearance));
      }
      if (textend)
      {
         int n = 0;
         char *p = strdupa (textend);
         while (p)
         {
            char *q = strchr (p, '\\');
            if (q)
               *q++ = 0;
            if (*p && n == (parts - part))
            {
               fprintf (out, "rotate([0,0,%f])", (part == parts ? 1 : -1) * (90 + (double) 180 / (outersides ? : 100)));
               cuttext (r2 - outerround, p, textfontend, 0);
            }
            p = q;
            n++;
         }
      }
      /**
       * Generates text on the outer sides of the puzzle box.
       * Text is positioned on each facet of the polygonal outer surface,
       * and can be either embossed or raised.
       * 
       * @param outset If 1, text is raised outward; if 0, text is embossed inward
       */
      void textside (int outset)
      {
         double a = 90 + (double) 180 / outersides;
         double h = r3 * sin (M_PI / outersides) * textsidescale / 100;
         char *p = strdupa (textsides);
         while (p)
         {
            char *q = strchr (p, '\\');
            if (q)
               *q++ = 0;
            if (*p)
            {
               fprintf (out, "rotate([0,0,%f])translate([0,-%lld,%lld])rotate([-90,-90,0])", a, scaled (r2),
                        scaled (outerround + (height - outerround) / 2));
               cuttext (h, p, textfont, outset);
            }
            a -= 360 / outersides;
            p = q;
         }
      }

      if (textsides && part == parts && outersides && !textoutset)
         textside (0);
      if (ajklogo && part == parts)
         fprintf (out, "translate([0,0,%lld])logo(%lld);\n", scaled (basethickness - logodepth), scaled (r0 * 1.8));
      else if (aalogo && part == parts)
         fprintf (out, "translate([0,0,%lld])linear_extrude(height=%lld,convexity=10)logo(%lld,white=true);\n",
                  scaled (basethickness - logodepth), scaled (logodepth * 2), scaled (r0 * 1.8));
      else if (textinside)
         fprintf
            (out,
             "translate([0,0,%lld])linear_extrude(height=%lld,convexity=10)text(\"%s\",font=\"%s\",size=%lld,halign=\"center\",valign=\"center\");\n",
             scaled (basethickness - logodepth), scaled (logodepth * 2), textinside, textfontend, scaled (r0));
      if (markpos0 && part + 1 >= parts)
         mark ();
      fprintf (out, "}\n");
      if (textsides && part == parts && outersides && textoutset)
         textside (1);
      if (coresolid && part == 1)
         fprintf (out, "translate([0,0,%lld])cylinder(r=%lld,h=%lld,$fn=%d);\n", scaled (basethickness), scaled (r0 + clearance + (!mazeinside && part < parts ? clearance : 0)), scaled (height - basethickness), W * 4);      // Solid core
      if ((mazeoutside && !flip && part == parts) || (!mazeoutside && part + 1 == parts))
         entrya = 0;            // Align for lid alignment
      else if (fixnubs)
      {
         entrya = globalexit + 180.0;  // Fixed position opposite maze exit (using global)
         if (entrya >= 360.0)
            entrya -= 360.0;
      }
      else if (part < parts && !basewide)
      {                         // We can position randomly
         int v;
         if (read (f, &v, sizeof (v)) != sizeof (v))
            err (1, "Read /dev/random");
         entrya = v % 360;
      }
      // Nubs
      /**
       * Generates the interlocking nubs that connect puzzle box parts.
       * Creates multiple nubs around the circumference using polyhedron geometry.
       * Nubs can be helical and have independently adjustable dimensions.
       * 
       * @param r Radius at which to place the nubs
       * @param inside If 1, nubs are on inside (protruding inward); if 0, on outside (protruding outward)
       */
      void addnub (double r, int inside)
      {
         double ri = r + (inside ? -mazethickness : mazethickness) * nubnormal;
         int W = ((int) ((ri + (inside ? -clearance : clearance)) * 2 * M_PI / mazestep)) / nubs * nubs;
         double da = (double) 2 * M_PI / W / 4 * nubhorizontal; // x angle per 1/4 maze step (scaled by nubhorizontal)
         double dz = (mazestep / 4 - nubzclearance) * nubvertical;
         double my = mazestep * da * 4 * helix / (r * 2 * M_PI);
         if (inside)
            da = -da;
         else if (mirrorinside)
            my = -my;           // This is nub outside which is for inside maze
         double a = -da * 1.5;  // Centre A
         double z = height - mazestep / 2 - (parkvertical ? 0 : mazestep / 8) - dz * 1.5 - my * 1.5;    // Centre Z
         fprintf (out, "rotate([0,0,%f])for(a=[0:%f:359])rotate([0,0,a])polyhedron(points=[", entrya, (double) 360 / nubs);
         r += (inside ? nubrclearance : -nubrclearance);        // Extra gap
         ri += (inside ? nubrclearance : -nubrclearance);       // Extra gap
         for (Z = 0; Z < 4; Z++)
            for (X = 0; X < 4; X++)
               fprintf (out, "[%lld,%lld,%lld],", scaled (((X == 1 || X == 2) && (Z == 1 || Z == 2) ? ri : r) * sin (a + da * X)),
                        scaled (((X == 1 || X == 2)
                                 && (Z == 1 || Z == 2) ? ri : r) * cos (a + da * X)), scaled (z + Z * dz + X * my + (Z == 1
                                                                                                                     || Z ==
                                                                                                                     2 ? nubskew :
                                                                                                                     0)));
         r += (inside ? clearance - nubrclearance : -clearance + nubrclearance);        // Back in to wall
         for (Z = 0; Z < 4; Z++)
            for (X = 0; X < 4; X++)
               fprintf (out, "[%lld,%lld,%lld],", scaled (r * sin (a + da * X)), scaled (r * cos (a + da * X)),
                        scaled (z + Z * dz + X * my + (Z == 1 || Z == 2 ? nubskew : 0)));
         fprintf (out, "],faces=[");
         for (Z = 0; Z < 3; Z++)
            for (X = 0; X < 3; X++)
               fprintf (out, "[%d,%d,%d],[%d,%d,%d],", Z * 4 + X + 20, Z * 4 + X + 21, Z * 4 + X + 17, Z * 4 + X + 20,
                        Z * 4 + X + 17, Z * 4 + X + 16);
         for (Z = 0; Z < 3; Z++)
            fprintf (out, "[%d,%d,%d],[%d,%d,%d],[%d,%d,%d],[%d,%d,%d],", Z * 4 + 4, Z * 4 + 20, Z * 4 + 16, Z * 4 + 4, Z * 4 + 16,
                     Z * 4 + 0, Z * 4 + 23, Z * 4 + 7, Z * 4 + 3, Z * 4 + 23, Z * 4 + 3, Z * 4 + 19);
         for (X = 0; X < 3; X++)
            fprintf (out, "[%d,%d,%d],[%d,%d,%d],[%d,%d,%d],[%d,%d,%d],", X + 28, X + 12, X + 13, X + 28, X + 13, X + 29, X + 0,
                     X + 16, X + 17, X + 0, X + 17, X + 1);
         fprintf (out, "[0,1,5],[0,5,4],[4,5,9],[4,9,8],[8,9,12],[9,13,12],");
         fprintf (out, "[1,2,6],[1,6,5],[5,6,10],[5,10,9],[9,10,14],[9,14,13],");
         fprintf (out, "[2,3,6],[3,7,6],[6,7,11],[6,11,10],[10,11,15],[10,15,14],");
         fprintf (out, "]);\n");
      }

      if (!mazeinside && part > 1)
         addnub (r0, 1);
      if (!mazeoutside && part < parts)
         addnub (r1, 0);
      fprintf (out, "}\n");
      x += (outersides & 1 ? r3 : r2) + r2 + 5;
      if (++n >= sq)
      {
         n = 0;
         x = 0;
         y += (outersides & 1 ? r3 : r2) * 2 + 5;
      }
   }

   fprintf (out, "scale(" SCALEI "){\n");
   if (part)
      box (part);
   else
      for (part = 1; part <= parts; part++)
         box (part);
   fprintf (out, "}\n");
   close (f);
   if (out != stdout)
      fclose (out);

   if (stl)
   {
      // OpenSCAD is a resource hog, so one at a time. Lock releases on file close on exit
      flock (open ("/var/lock/puzzlebox", O_CREAT, 0666), LOCK_EX);
      char tmp2[] = "/tmp/XXXXXX.stl";
      if (!outfile)
      {
         int o = mkstemps (tmp2, 4);
         if (o < 0)
            err (1, "Bad tmp");
         close (o);
      }
      pid_t pid = fork ();
      if (pid < 0)
         err (1, "bad fork");
      if (!pid)
      {                         // Child
         execlp ("openscad", "openscad", "-q", tmp, "-o", outfile ? : tmp2, NULL);
         exit (0);
      }
      int status = 0;
      waitpid (pid, &status, 0);
      unlink (tmp);
      if (!WIFEXITED (status) || WEXITSTATUS (status))
      {
         unlink (tmp2);
         errx (1, "openscad failed");
      }
      if (!outfile)
      {                         // To stdout
         int i = open (tmp2, O_RDONLY);
         unlink (tmp2);
         if (i < 0)
            err (1, "Cannot open %s", tmp2);
         char buf[1024];
         int l;
         while ((l = read (i, buf, sizeof (buf))) > 0)
            write (STDOUT_FILENO, buf, l);
         close (i);
      }
      
      // Create metadata file with command line parameters and maze data
      if (outfile && mazedata && mazedatasize > 0)
      {
         char *metafile = NULL;
         if (asprintf (&metafile, "%s.meta", outfile) < 0)
            err (1, "Failed to create metadata filename");
         
         FILE *meta = fopen (metafile, "w");
         if (meta)
         {
            fprintf (meta, "Puzzlebox Metadata\n");
            fprintf (meta, "==================\n\n");
            fprintf (meta, "Generated by: puzzlebox (RevK)\n");
            fprintf (meta, "GitHub: https://github.com/revk/PuzzleBox\n\n");
            
            // Timestamp
            time_t now = time (0);
            struct tm t;
            gmtime_r (&now, &t);
            fprintf (meta, "Created: %04d-%02d-%02dT%02d:%02d:%02dZ\n\n",
                     t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec);
            
            // Command line parameters
            fprintf (meta, "Command Line Parameters\n");
            fprintf (meta, "-----------------------\n");
            int o;
            for (o = 0; optionsTable[o].longName; o++)
               if (optionsTable[o].shortName && optionsTable[o].arg)
                  switch (optionsTable[o].argInfo & POPT_ARG_MASK)
                  {
                  case POPT_ARG_NONE:
                     if (*(int *) optionsTable[o].arg)
                        fprintf (meta, "%s: enabled\n", optionsTable[o].descrip);
                     break;
                  case POPT_ARG_INT:
                     {
                        int v = *(int *) optionsTable[o].arg;
                        if (v)
                           fprintf (meta, "%s: %d\n", optionsTable[o].descrip, v);
                     }
                     break;
                  case POPT_ARG_DOUBLE:
                     {
                        double v = *(double *) optionsTable[o].arg;
                        if (v)
                           fprintf (meta, "%s: %g\n", optionsTable[o].descrip, v);
                     }
                     break;
                  case POPT_ARG_STRING:
                     {
                        char *v = *(char * *) optionsTable[o].arg;
                        if (v && *v)
                           fprintf (meta, "%s: %s\n", optionsTable[o].descrip, v);
                     }
                     break;
                  }
            fprintf (meta, "\n");
            
            // Maze data
            fprintf (meta, "\n");
            fwrite (mazedata, 1, mazedatasize, meta);
            fclose (meta);
         }
         free (metafile);
      }
   }
   if (mazedata)
      free (mazedata);
   return 0;
}
