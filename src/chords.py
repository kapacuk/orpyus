# new chord class with explicit factor recognition and compositional name generation/recognition

# import notes
from .notes import Note, NoteList, chromatic_scale, relative_minors, relative_majors, sharp_minor_tonics, sharp_major_tonics, flat_minor_tonics, flat_major_tonics
from .intervals import Interval, IntervalList, P5
from .util import log, precision_recall, rotate_list, check_all, auto_split, reverse_dict, unpack_and_reverse_dict
from . import parsing
from . import qualities
from .qualities import Quality, ChordQualifier, parse_chord_qualifiers

from collections import defaultdict

from pdb import set_trace




class ChordFactors(dict):
    """a class representing the factors of an AbstractChord, as a dict which has:
        keys: chord degrees (1 representing the root, 5 representing the fifth, etc.)
        values: semitone offsets from default degree intervals.
            e.g. the fifth degree is 7 semitones by default, so {5: -1} implies
            a fifth that is diminished (-1 from perfect), i.e. 6 semitones from root.
        qualifiers: a list of Qualifier objects that have been applied to this object.
            note these are not qualifiers that *should* be applied, but a history for this object.
            applying qualifiers must be done using the __add__ method, or the qualifier's .apply method"""

    def __init__(self, arg=None, qualifiers=None):
        """accepts any arg that would initialise a dict,
          and also allows a string of degree alterations (e.g. "1-♭3-♭♭5")
          or a list of such alterations (e.g. ["1", "♭3", "♭♭5"])
        also treats init by None (i.e. no args) as a major triad by default."""

        # accept re-casting by dict comp:
        if isinstance(arg, ChordFactors):
            arg = {k:v for k,v in arg.items()}

        ### allow initialisation by string or list of chord degrees:
        if isinstance(arg, str):
            ### parse string into list of accidentals by auto splitting non-accidentals
            arg = auto_split(arg, allow='#♯𝄪b♭𝄫/')

        if isinstance(arg, list) and type(arg[0]) != tuple:
            # parse a list of non-tuples (i.e. invalid list for dict input) as list of chord degrees
            dict_arg = {}
            for item in arg:
                assert isinstance(item, str)
                # this is an
                qual_dict = parsing.parse_alteration(item)
                dict_arg.update(qual_dict)
            arg = dict_arg
            # then continue as normal

        if arg is None:
            # default init with no input args is a major triad:
            arg = {1:0, 3:0, 5:0}

        super().__init__(arg)
        # # sanity check:
        # for k, v in self.items():
        #     assert isinstance(k, int) and (k >= 1)
        #     assert isinstance(v, int) and (-2 <= v <= 2)
        if qualifiers is None:
            self.qualifiers = []
        else:
            self.qualifiers = list(qualifiers)

    @property
    def degrees(self):
        return list(self.keys())

    @property
    def offsets(self):
        return list(self.values())

    @property
    def order(self):
        """the number of notes in the chord that this object represents"""
        return len(self)

    def to_intervals(self, as_dict=False):
        """translates these ChordFactors into an IntervalList
        or, if as_dict, into a factor_intervals dict mapping degrees to intervals"""
        if not as_dict:
            return IntervalList([Interval.from_degree(d, offset=o) for d, o in self.items()]).sorted()
        elif as_dict:
            return {d:Interval.from_degree(d, offset=o) for d, o in self.items()}

    def copy(self):
        return ChordFactors({k:v for k,v in self.items()}, qualifiers=self.qualifiers)

    def __add__(self, other):
        """modifies these factors by the alterations in a ChordQualifier,
        return new factors object."""
        # output_factors = ChordFactors(self, qualifiers=self.qualifiers)

        if isinstance(other, ChordQualifier):
            output_factors = other.apply(self)
            # output_factors.qualifiers.append(other)
        elif isinstance(other, (list, tuple)):
            # apply a list of ChordQualifiers instead:
            output_factors = self.copy()
            for qual in other:
                assert isinstance(qual, ChordQualifier), f"ChordFactor tried to be modified by an item in a list that was not a ChordQualifier but was: {type(qual)}"
                output_factors = qual.apply(output_factors)
                # output_factors.qualifiers.append(qual)
        # ensure that we keep ourselves sorted:
        else:
            raise TypeError(f'Cannot add ChordFactors object to type: {type(other)}')
        sorted_keys = sorted(list(output_factors.keys()))
        # return output_factors
        return ChordFactors({k: output_factors[k] for k in sorted_keys}, qualifiers = output_factors.qualifiers)

    def distance(self, other):
        # distance from other ChordFactors objects, to detect altered chords from their factors
        # as qualifier: what must be done to RIGHT (other) to make it LEFT (self)
        assert isinstance(self, ChordFactors) and isinstance(other, ChordFactors)
        add, modify, remove  = {}, {}, []
        for degree, offset in self.items():
            if degree not in other:
                # other must add this degree at this value
                add[degree] = offset
            elif offset != other[degree]:
                other_offset = other[degree]
                offset_dist = offset - other_offset
                modify[degree] = offset_dist
        for degree in other.keys():
            if degree not in self:
                remove.append(degree)
        dist_qualifier = ChordQualifier(add=add, modify=modify, remove=remove)
        return dist_qualifier

    def __sub__(self, other):
        """the - operator calculates (symmetric) distance between ChordFactors"""
        return self.distance(other)

    def __hash__(self):
        return hash(tuple(self))

    def __str__(self):
        factor_strs = [f'{parsing.offset_accidentals[v][0]}{d}' for d,v in self.items()]
        return f'¦ {", ".join(factor_strs)} ¦'

    def __repr__(self):
        return f'ChordFactors: {str(self)}'

# a chord's factors look like this:
_major_triad = ChordFactors({1:0, 3:0, 5:0})
# meaning: default intervals of 1st, 3rd, and 5th degrees
# this _major_triad object is used for comparisons, but should never be modified

################################################################################

class AbstractChord:
    """a hypothetical chord not built on any specific note but having all the qualifiers that a chord would,
    whose principal members are Intervals. see AbstractChord._parse_input for valid input schemas.
    an AbstractChord is fully identified by its Factors and its Inversion."""
    def __init__(self, name=None, factors=None, intervals=None, inversion=None, inversion_degree=None, qualifiers=None):
        """primary input arg must be one of the following mutually exclusive keywords, in order of resolution:
        1. 'name' arg as string denoting the name of an AbstractChord (like 'mmaj7'),
                which we look up and parse as a list of ChordQualifiers.
                  --this name can also contain an inversion (like 'mmaj7/2'), which
                    we interpret as an 'inversion' arg (and therefore ignore an
                    inversion kwarg if one has been supplied)
        2. (re-casting): 'name' arg of type AbstractChord, or a subclass of AbstractChord, from which
                we read the factors/intervals/inversion directly.
        3. 'factors' arg of type ChordFactors, keying degree to semitone offsets,
                which we accept directly.
        4. 'intervals' arg as list of Intervals, or ints that cast to Intervals, which we
            interpret as distances from the desired chord's root (using Interval.degree
                attribute to build ChordFactors from)

        and special case:
        5. 'qualifiers' arg as string or list of ChordQualifier objects, (or objects that cast
                to ChordQualifiers), which we successively apply to the major triad.
        this can be given as sole init argument, but is also valid to provide in combination
            with any of the other keyword args, in which case we apply the qualifiers
            not to the major triad, but whatever other chord got parsed out by the keyword arg.

        lastly, an optional arg: one of 'inversion' or 'inversion_degree':
            'inversion' as int, denoting that this chord is an "Xth inversion", meaning that
                the bass note is the X+1th note in the chord, with notes ordered ascending.
        or
            'inversion_degree' as int, denoting the degree that the chord's bass note is on.

        note that both are ignored if the 'name' arg contains a slash."""

        self.factors, self.root_intervals, self.inversion = self._parse_input(name, factors, intervals, inversion, inversion_degree, qualifiers)

        # dict mapping chord factors to intervals from tonic (and vice versa):
        self.factor_intervals = {i.extended_degree: i for i in self.root_intervals}
        self.interval_factors = reverse_dict(self.factor_intervals)

        if self.inversion != 0: # list of self.intervals is with respect to this chord's inversion
            self.intervals = self.root_intervals.invert(self.inversion)
        else:
            self.intervals = self.root_intervals

        self.quality = self._determine_quality()


    def _parse_input(self, name, factors, intervals, inversion, inversion_degree, qualifiers, _allow_note_name=False):
        """takes valid inputs to AbstractChord and parses them into factors, intervals and inversion.
        (see docstring for AbstractChord.__init__)"""

        if isinstance(name, list):
            # we've been fed a list, probably of integers or intervals:
            if (type(name) == IntervalList) or (type(name) == list and check_all(name, 'isinstance', (int, Interval))):
                # we've been fed an IntervalList as first (name) arg, which we quietly re-cast:
                assert intervals is None
                intervals = name
                name = None
            else:
                raise ValueError(f'AbstractChord expected a string but was initialised with a list as first arg, and it does not seem to be a valid IntervalList: {name}')

        if name is None and factors is None and intervals is None:
            # we have been given nothing to init by, so initialise a basic major triad:
            factors = ChordFactors()

        if name is not None:
            assert factors is None and intervals is None
            # check for inversion by slashes: (or sometimes backslashes)
            if '/' in name or '\\' in name:
                assert inversion is None and inversion_degree is None, 'Parsed slash chord as denoting inversion, but received mutually exclusive inversion arg'
                # parse inversion from name
                name = name.replace('\\', '/')
                name, inversion_str = name.split('/')

                if inversion_str.isnumeric():
                    inversion = int(inversion_str)
                else:
                    assert _allow_note_name, f'String inversions only allowed for non-AbstractChords'
                    inversion = inversion_str

            # detect if name refers to a major chord:
            if name == '' or name in ((qualities.qualifier_aliases['maj']) + ['maj']):
                factors = ChordFactors() # major triad by default
            else:
                qualifiers_from_name = parse_chord_qualifiers(name)
                factors = ChordFactors() + qualifiers_from_name
        elif factors is not None:
            assert name is None and intervals is None
            # do nothing! factors are already defined, just pass to next block
        elif intervals is not None:
            assert name is None and factors is None
            # sanitise interval list input, expect root to be provided:

            # if it is a list of ints, catch common thirds/fifths:
            if isinstance(intervals, (tuple, list)) and check_all(intervals, 'isinstance', int):
                sanitised_intervals = []
                for i in intervals:
                    if i in {3,4}: # could this be a major/minor third?
                        sanitised_intervals.append(Interval(i, degree=3))
                    elif i in {6,7,8}: # could this be a dim/perf/aug fifth?
                        sanitised_intervals.append(Interval(i, degree=5))
                    else:
                        sanitised_intervals.append(i)
                intervals = sanitised_intervals

            # cast to IntervalList object, pad to canonical chord intervals form with left bass root but not upper octave root
            intervals = IntervalList(intervals).pad(left=True, right=False)
            assert len(intervals) == len(set(intervals)), f'Interval list supplied to AbstractChord init contains repeated intervals: {intervals}'

            # check if this is an inversion of some common chord:
            if intervals in intervals_to_chord_names:
                # (we'll use the inversion only if it's less rare than the root intervals)
                supplied_interval_chord_name = intervals_to_chord_names[intervals]
                supplied_rarity = chord_name_rarities[supplied_interval_chord_name]
            else:
                supplied_rarity = 10 # max possible

            # search for possible inversions if this is not already one,
            # and adopt the most common, if it's more common than what we've been given:
            if inversion is None and inversion_degree is None:
                possible_inversions = AbstractChord.inversions_from_intervals(intervals)
                if len(possible_inversions) > 0 and possible_inversions[0].rarity < supplied_rarity:
                    # adopt the inverted chord's root intervals and inversion instead
                    intervals = possible_inversions[0].root_intervals
                    inversion = possible_inversions[0].inversion
                    # and one last change (bit of a kludge): if this is a Chord, intercept and change the root:
                    if isinstance(self, Chord):
                        self.root -= intervals[inversion]
                else:
                    # we've failed to find an inversion, so just use the intervals and root as they are
                    if intervals not in intervals_to_chord_names:
                        log(f'Failed to find a matching chord or inversion for intervals: {intervals}')

            # build factors by looping through intervals:
            factors = ChordFactors({1:0}) # note: NOT a major triad
            mod_factors_used = set()
            for i in intervals: # parse interval degree and quality into factors dict
                # if i.mod != 0: # catch special case: do not record perfect octaves
                # count the mod intervals we've already used, so we ignore adding them if they come up again:
                # (this ensures that e.g. 'CEGCGEC' is parsed as 'CEG')
                if i.mod not in mod_factors_used:
                    factors[i.extended_degree] = i.offset_from_default
                    mod_factors_used.add(i.mod)

        if qualifiers is not None:
            if factors is None:
                # start qualifying a major triad by default
                factors = ChordFactors()

            if isinstance(qualifiers, str):
                # parse string of qualifiers as an iterable of them
                qualifiers = parse_chord_qualifiers(qualifiers)
            # make sure we're dealing with an iterable of them:
            check_all(qualifiers, 'isinstance', ChordQualifier)
            # apply them to our factors:
            factors = factors + qualifiers

        if intervals is None: # i.e. if we have defined factors from name or factor kwarg
            # in this case we trust them and do not insist that this is an inversion
            # i.e. we keep 6(no5) instead of casting to m/2
            intervals = []
            for deg, offset in factors.items():
                # note that interval list always includes Unison as root
                intervals.append(Interval.from_degree(deg, offset=offset))
            intervals = IntervalList(intervals)

        if inversion_degree is not None:
            # which Xth inversion is this, from the inversion degree:
            for x, deg in enumerate(sorted(factors.keys())):
                if inversion_degree == deg:
                    inversion = x
                    break

        if (inversion is not None) and (inversion != 0):
            if isinstance(inversion, int):
                assert 0 < inversion <= (len(factors)-1), f'{inversion} is an invalid inversion number for chord with {len(factors)} factors'
            elif isinstance(inversion, str):
                if not _allow_note_name:
                    raise TypeError(f'inversion arg for AbstractChord must be an int, but got: {type(inversion)}')
                else:
                    if not parsing.is_valid_note_name(inversion):
                        raise ValueError(f'got string argument to inversion, but does not seem to be a valid note name: {inversion}')
            else:
                raise TypeError(f'inversion must be an int or str, but got: {type(inversion)}')
        else:
            inversion = 0 # 0th inversion means no inversion at all

        return factors, intervals.sorted(), inversion

    def _determine_quality(self):
        # quality of a chord is the quality of its third:
        if 3 not in self.factors:
            # use the quality of the 5th: usually perfect, but could be a dim5(no3) or something
            return self.factor_intervals[5].quality
        else:
            if self.factor_intervals[3].quality.major:
                # is augmented if the 5th is augmented, otherwise is major
                if 5 in self.factors and self.factor_intervals[5].quality.augmented:
                    return qualities.Augmented
                else:
                    return qualities.Major
            elif self.factor_intervals[3].quality.minor:
                if 5 in self.factors and self.factor_intervals[5].quality.diminished:
                    return qualities.Diminished
                else:
                    return qualities.Minor
            else:
                # third is present but neither major or minor, meaning it is dim or aug (or ddim or aaug)
                # so we'll just call this chord whatever the third is:
                return self.factor_intervals[3].quality

    def __len__(self):
        return len(self.factors)

    @property
    def _inv_string(self):
        """inversion string, used internally by suffix method (and inherited by subclasses)"""
        return f'/{self.inversion}' if (self.inversion != 0) else ''

    @property
    def suffix(self):
        return self.get_suffix(inversion=True)

    def get_suffix(self, inversion=True):
        """dynamically determine chord suffix from factors and inversion"""
        inv_string = self._inv_string if inversion else ''
        if self.factors in factors_to_chord_names:
            return factors_to_chord_names[self.factors] + inv_string
        elif self.root_intervals in intervals_to_chord_names:
            suf = intervals_to_chord_names[self.root_intervals] + inv_string
            log(f' ++ Could not find chord by factors ({self.factors}), but found it by root intervals ({self.root_intervals}): {suf}')
            return suf
        elif self.intervals in intervals_to_chord_names:
            # set_trace(context=30) # can't remember what is going on here
            print(f' ++++ Could not find chord by factors ({self.factors}), but found it by inverted intervals: {self.intervals}')
            import pdb; pdb.set_trace() # in case this ever comes up
            return intervals_to_chord_names[self.intervals] + f' (inverted from {self.root})'
        elif 5 not in self.factors:
            # try adding a 5 to see if this is a (no5) chord
            intervals_with_5 = IntervalList(sorted(list(self.root_intervals) + [P5]))
            if intervals_with_5 in intervals_to_chord_names:
                return intervals_to_chord_names[intervals_with_5] + '(no5)' + inv_string
            # try the same for this chord's inversions? (this gets messy very fast)

        # try flattening intervals and seeing if that produces a chord: (i.e. parsing CGE as CEG)
        if self.intervals.flatten() in intervals_to_chord_names:
            return intervals_to_chord_names[self.intervals.flatten()]
        elif self.factors == _major_triad:
            return ''
        elif self.assigned_name is not None:
            # fall back on name given to an exotic chord like Am7/B if one was assigned
            return self.assigned_name
        else:
            return f'(?){inv_string}'

    @property
    def rarity(self):
        """an integer denoting how rarely this chord is used in practice"""
        return chord_name_rarities[factors_to_chord_names[self.factors]]

    @property
    def likelihood(self):
        """converse of rarity, likelihood score as a float between 0-1"""
        l_score = (10-self.rarity)/10
        # with a penalty for inversions:
        if self.inversion != 0:
            l_score -= 0.15
        return l_score

    def identify_inversion(self):
        """searches all of this chord's possible inversions to see if one of them
        matches an existing chord, and returns that chord's inversion as a new object"""
        return self.inversions_from_intervals(self.intervals)

    def get_pairwise_intervals(self, extra_tonic=False):
        pairwise = {}
        for i in range(len(self.intervals)):
            for j in range(i+1, len(self.intervals)):
                pairwise[(self.intervals[i], self.intervals[j])] = self.intervals[j] - self.intervals[i]
                if extra_tonic:
                    raise Exception('not implemented')
        return pairwise
    @property
    def pairwise_intervals(self):
        return self.get_pairwise_intervals(extra_tonic=False)

    def get_pairwise_consonances(self, extra_tonic=False):
        pw_intervals = self.get_pairwise_intervals(extra_tonic=extra_tonic)
        pw_consonances = {}
        for pair, diff in pw_intervals.items():
            pw_consonances[pair] = diff.consonance
        return pw_consonances
    @property
    def pairwise_consonances(self):
        return self.get_pairwise_consonances()

    @property
    def consonance(self, tonic_weight=2):
        """the weighted mean of pairwise interval consonances"""
        cons_list = []
        for pair, cons in self.pairwise_consonances.items():
            if (tonic_weight != 1) and (pair[0].value == 0): # intervals from root are counted double
                cons_list.extend([cons]*tonic_weight)
            else:
                cons_list.append(cons)
        raw_cons = sum(cons_list) / len(cons_list)

        # the raw consonance comes out as maximum=0.933 (i.e. 14/15) for the most consonant chord (the octave)
        # by definition because of the constant 15 in the interval dissonance calculation, where
        # perfect consonance (unison) has dissonance 0 and the octave has dissonance 1.

        # chords cannot be on unison, so we'll set the ceiling to 1 instead of 0.9333.

        # and the empirically observed minimum is just above 0.49 for the awful tritone plus minor ninth
        # so we set that to be just around 0, and rescale the entire raw consonance range within those bounds:
        max_cons = 14/15
        min_cons = 0.49
        rescaled_cons = (raw_cons - min_cons) / (max_cons - min_cons)
        return round(rescaled_cons, 3)

    @staticmethod
    def inversions_from_intervals(intervals):
        """searches an interval list's inversions for possible matching chords
        and returns as a dict keying candidate inverted AbstractChords to their rarities"""
        candidates = []
        for inversion_place in range(1, len(intervals)):
            inverted_intervals = intervals.invert(-inversion_place)
            if inverted_intervals in intervals_to_chord_names:
                that_chord_name = intervals_to_chord_names[inverted_intervals]
                candidates.append(AbstractChord(that_chord_name, inversion=inversion_place))
        candidates.sort(key = lambda x: x.rarity)
        return candidates

    @property
    def short_name(self):
        if '/' in self.suffix:
            suffix, inv = self.suffix.split('/')
            inv = f'/{inv}'
        else:
            suffix, inv = self.suffix, ''
        if suffix == '':
            # unique to AbstractChord: report major and dominant suffix
            return f'maj{inv}'
        elif suffix.isnumeric() and suffix not in {'5', '6'}: # dominant chords (which are not 5s or 6s)
            return f'dom7{inv}'
        else:
            return f'{suffix}{inv}'

    @property
    def name(self):
        return f'{self.short_name} chord'

    def invert(self, inversion=None, inversion_degree=None):
        """returns a new AbstractChord based off this one, but inverted.
        not to be confused with self.__invert__!"""
        return AbstractChord(factors=self.factors, inversion=inversion, inversion_degree=inversion_degree)

    def on_root(self, root_note):
        """constructs a Chord object from this AbstractChord with respect to a desired root"""
        return Chord(root=root_note, factors=self.factors, inversion=self.inversion)

    def on_bass(self, bass_note):
        """constructs an inverted Chord object from this inverted AbstractChord with respect to a desired bass"""
        if self.inversion == 0:
            # bass is root, so on_bass is equivalent to on_root:
            return self.on_root(bass_note)
        else:
            # construct the root note from the desired bass note and this AbstractChord's inversion:
            root_to_bass_interval = self.root_intervals[self.inversion]
            root_note = Note(bass_note) - root_to_bass_interval
            return Chord(root=root_note, factors=self.factors, inversion=self.inversion)

    def __len__(self):
        """this chord's order, i.e. the number of notes/factors"""
        return len(self.factors)

    @property
    def order(self):
        return len(self)

    def __add__(self, other):
        """Chord + Chord results in a ChordList (which can further be analysed as a progression)
        Chord + Note adds the note to produce a new Chord
        Chord + Interval produces a new chord that is transposed by that Interval"""
        if isinstance(other, str):
            # parse if this str is a note or a chord, preferring note first:
            if parsing.is_valid_note_name(other):
                other = Note(other)
            else:
                other = Chord(other)

        if isinstance(other, Chord):
            # concatenation of chords to produce ChordList (or ChordProgression?):
            from .progressions import ChordList, ChordProgression # lazy import
            return ChordList([self, other])

        if isinstance(other, Note):
            # addition of new note to produce new chord:
            new_notes = list(self.notes) + [other]
            return Chord(notes=new_notes)

        elif isinstance(other, (int, Interval)):
            # transposition by int/interval:
            new_root = self.root + int(other)
            return Chord(factors=self.factors, root=new_root)

    def __sub__(self, other):
        pass # TBI, but should include subtraction by interval, subtraction by note (deletion), or by chord (difference/distance)
        if isinstance(other, str):
            if parsing.is_valid_note_name(other):
                other = Note(other)
            elif parsing.begins_with_valid_note_name(other):
                other = Chord(other)

        if isinstance(other, Note):
            # note deletion
            new_notes = [n for n in self.notes if n != other]
            return Chord(notes=new_notes)

        elif isinstance(other, Chord):
            return self.chord_distance(other) # Not Yet Implemented

        elif isinstance(other, (int, Interval)):
            new_root = self.root - int(other)
            return Chord(root=new_root, factors=self.factors, inversion=self.inversion)

        else:
            raise TypeError(f'Chord.__sub__ not defined for type: {type(other)}')


    @property
    def _marker(self):
        """unicode character marker identifying this class"""
        return '♫'

    def __str__(self):
        return f'{self._marker} {self.name}'

    def __repr__(self):
        # note that intervals are presented with respect to inversion
        interval_short_names = [i.short_name for i in self.intervals]
        intervals_str = ', '.join(interval_short_names)
        return f'{str(self)} | {intervals_str} |'
        # return str(self)

    def __contains__(self, item):
        """AbstractChords can contain degrees (as integers), or intervals (as Intervals)"""
        if isinstance(item, Interval):
            return item in self.intervals # note: uses inverted intervals, not root position
        elif isinstance(item, int):
            return item in self.factors.keys()
        else:
            raise TypeError(f'AbstractChord object cannot contain items of type: {type(item)}')

    def __eq__(self, other):
        """AbstractChords are equal to others on the basis of their factors and inversion"""
        if type(other) == AbstractChord:
            return (self.factors == other.factors) and (self.inversion == other.inversion)
        else:
            raise TypeError(f'AbstractChords can only be compared to other AbstractChords')

    def __hash__(self):
        return hash(((tuple(self.factors.items())), self.inversion))

################################################################################

class Chord(AbstractChord):
    """a Chord built on a note of the chromatic scale, but in no particular octave.
            shares all of the attributes/methods of AbstractChord,
            but additionally has a root and a note list. (and a sharp/flat preference)
            if inverted, also stores bass note, and note list in inverted position.
    """
    def __init__(self, name=None,
                       root=None, factors=None, intervals=None, notes=None,
                       inversion=None, inversion_degree=None, bass=None,
                       qualifiers=None,
                       in_key=None, prefer_sharps=None,
                       recursive_reinit=True):
        """initialised in one of three ways:

        1. from 'notes' arg, as a list of Notes (or a note-string),
            in which case we set the first Note as the root,
            and initialise the remaining intervals as with an AbstractChord.

        2. from 'name' arg, as a proper Chord name (like "Csus2" or "Ebminmaj7"),
            in which case we extract the root note from the string, and initialise
            the remaining suffix as with an AbstractChord.
                name can also specify an inversion, such as: "Csus2/D", which
                overwrites explicit inversion args (see below)

        3. from 'root' arg, as a Note object (or an object that casts to a Note),
            in combination with any of the keyword args that would initialise an AbstractChord,
            i.e. one of 'factors', 'intervals', or 'name'.

        if a NoteList, or IntervalList, or ChordFactors object is fed as first arg (name),
            we'll try to detect that and re-parse the args appropriately.
            we'll even check if name is a valid note-string, like Chord('CEA').

        for any initialisation method, an inversion can also be specified
            (unless a slash chord name was used). this must be one of:

                a) 'inversion', the index of the bass note with respect to root.
                    (same as common musical term: "Cm, 2nd inversion" is Cm/G)

                b) 'inversion_degree', the degree of the bass note.

        we also accept the optional 'in_key' argument (TBI), instead of AbstractChord's 'in_scale',
        which specifies that this Chord is to be regarded as in a specific Key,
        affecting its sharp preference and arithmetic behaviours."""

        # if prefer_sharps is not given, we parse the name to see if we've been asked for it:
        if prefer_sharps is None and isinstance(name, str):
            # have we been given the name of a tonic note with a sharp in it?
            if '#' in name[1:3]:
                # prefer_sharps = ('#' in name[1:3])
                prefer_sharps = True

        # re-parse args to detect if 'name' is a list of notes, a list of intervals, or a dict of chordfactors:
        name, root, factors, intervals, notes = self._reparse_args(name, root, factors, intervals, notes)

        if notes is not None: # initialise from ascending note list by casting notes as intervals from root
            # ignore intervals/factors/root inputs
            assert root is None and factors is None and intervals is None
            assert name is None # but allow inversions
            note_list = NoteList(notes)
            # recover intervals and root, and continue to init as normal:
            intervals = NoteList(notes).ascending_intervals()
            root = note_list[0]

        # if name is a proper chord name like 'C' or 'Amaj' or 'D#sus2', separate it out into root and suffix components:
        self.root, suffix = self._parse_root(name, root)

        assert self.root is not None

        # allow inversion by bass keyword arg, by reallocating into inversion arg for _parse_input:
        if bass is not None:
            assert inversion is None
            inversion = Note(bass).name

        # recover factor offsets, intervals from root, and inversion position from input args:
        self.factors, self.root_intervals, inversion = self._parse_input(suffix, factors, intervals, inversion, inversion_degree, qualifiers, _allow_note_name=True)
        # note that while self.inversion in AbstractChord comes out as strictly int or None
        # here we allow it to be a string denoting the bass note, which we'll correct in a minute

        # mapping of chord factors to intervals from tonic:
        self.factor_intervals = {i.extended_degree: i for i in self.root_intervals}
        self.interval_factors = reverse_dict(self.factor_intervals)
        # mapping of chord factors to notes:
        self.factor_notes = {degree: (self.root + i) for degree, i in self.factor_intervals.items()}
        self.note_factors = reverse_dict(self.factor_notes)

        # list of notes inside this chord, in root position:
        self.root_notes = NoteList(self.factor_notes.values())

        # discover the correct inversion parameters, as well as inverted notes / intervals if they differ from root position:
        inv_params, self.notes, self.intervals = self._parse_inversion(inversion, recursive_reinit=recursive_reinit)

        self.inversion, self.inversion_degree, self.bass = inv_params

        # quality of a chord is the quality of its third:
        self.quality = qualities.Perfect if 3 not in self.factors else self.factor_intervals[3].quality

        # set sharp preference based on root note:
        self._set_sharp_preference(prefer_sharps) ### TBI: move this up and make it affect root_notes etc. as well?

    @staticmethod
    def _reparse_args(name, root, factors, intervals, notes):
        """re-parse args to detect if 'name' is a list of notes, a list of intervals, or a dict of chordfactors,
        and returns the appropriate 'corrected' args if so."""
        # accept re-casting if name is just another Chord object:
        if isinstance(name, Chord):
            # initialise by input chord's name: (which contains its inversion information)
            assert (factors, intervals, notes) == (None, None, None), f'tried to initialise Chord object from another chord but with conflicting factors/intervals/notes arg'
            name = name.name
        # is name an IntervalList, or a list that contains only Intervals/ints:
        if isinstance(name, IntervalList) or (isinstance(name, (list, tuple)) and check_all(name, 'isinstance', (int, Interval))):
            assert intervals is None, f'list of Intervals was passed as first input to Chord init, but intervals arg was also given'
            intervals = name
            name = None
        # is name a NoteList, or a list that contains only Notes/strings:
        elif isinstance(name, NoteList) or (isinstance(name, (list, tuple)) and check_all(name, 'isinstance', (str, Note))):
            assert notes is None, f'list of Notes was passed as first input to Chord init, but notes arg was also given'
            notes = name
            name = None
        elif isinstance(name, str):
            ### here we must distinguish if name is a potential note_string, of the kind we can parse out
            parse_result = parsing.parse_out_note_names(name, graceful_fail=True)
            if parse_result is not False and len(parse_result) >= 2: # we don't allow note_strings for chord init unless they contain 2 or more notes
                notes = parse_result
                name = None
            else:
                # this is not a note_string, so just return the args as they came
                pass

        return name, root, factors, intervals, notes

    @staticmethod
    def _parse_root(name, root):
        """takes the class's name and root args, and determines which has been given.
        returns root as a Note object, and chord suffix as string or None"""
        if name is not None:
            root_name, suffix = parsing.note_split(name)
            root = Note(root_name)
        elif root is not None:
            root = Note(root)
            suffix = name
        else:
            raise Exception('neither name nor root provided to Chord init, we need one or the other!')
        return root, suffix


    def _parse_inversion(self, inversion, recursive_reinit=True):
        """given an inversion as int (Xth inversion) or string (bass note),
        return canonical forms: (inversion, inversion_degree, bass)
        with respect to already-defined self.root_notes"""
        if inversion == 0:
            inversion_degree = None
            # inversion = inversion_degree = None
            # no inversion, so the bass is just the root, and the notes/intervals are in root position:
            bass = self.root
            inverted_notes, inverted_intervals = self.root_notes, self.root_intervals

            inv_params = (inversion, inversion_degree, bass)
            return (inv_params), inverted_notes, inverted_intervals

        elif isinstance(inversion, int):
            assert 0 < inversion <= (len(self.factors)-1), f'{inversion} is an invalid inversion number for chord with {len(self.factors)} factors'
            inversion_degree = self.root_intervals[inversion].degree
            bass = self.root_notes[inversion]
        elif isinstance(inversion, (Note, str)):
            bass = Note(inversion)

            ####################################################################

            ### here we catch a special case: inversion over a bass note that is not in the specified chord.
            # e.g. something like Chord('D/C#') - it is not really a D major chord,
            # but a voicing of Dmaj7 or something

            if bass not in self.factor_notes.values():
                log(f"    Chord initialised with inversion over {bass}, \n    but {bass} is not in this chord's notes: {list(self.factor_notes.values())}")
                log(f"    Decomposing and reidentifying using recursive init")
                log(f'     Existing root intervals: {self.root_intervals}')
                bass_distance_from_root = bass - self.root

                if bass_distance_from_root < self.root_intervals[-1]:
                    ### e.g. for Am/C case
                    if not recursive_reinit:
                        log('     Bass note above root would not be above the highest interval in this chord, ')
                        log('      so we shift it up an octave and call it an inversion')
                        bass_distance_from_root += 12  # raise bass-note interval by an octave
                        new_intervals = IntervalList(list(self.root_intervals) + [bass_distance_from_root]) # add bass note to top of chord
                        # recursively re-initialise:
                        self.__init__(intervals=new_intervals, root=self.root, bass=bass)
                        return self._parse_inversion(bass.name)
                    else:
                        # trigger chord reidentification from notes
                        naive_chord_name = factors_to_chord_names[self.factors]

                        log(f"  Warning: Problem initialising chord: {self.root.name}{naive_chord_name} with notes: {self.root_notes}")
                        # print(f"  Initialised as inversion {self.root.name}{naive_chord_name}/{bass.name} but {bass} is not in the chord")
                        # print(f"  And it does not fit on top of the chord, so this is not a normal inversion of an extension")
                        # print(f"  So this is probably an unusual voicing of a non-inverted chord, with supplied bass note as root.")
                        try:
                            new_notes = NoteList([bass] + [n for n in self.root_notes])
                            log(f"  --Re-identifying chord from notes: {new_notes}")
                            if log.verbose:
                                new_notes.matching_chords(invert=False, min_precision=0.7, min_recall=0.8, min_likelihood=0, display=True)
                            likely_chord, stats = new_notes.most_likely_chord(invert=False, require_root=True, min_likelihood=0, stats=True)
                            if stats['precision'] == 1 and stats['recall'] == 1:
                                log(f"\n  --Identified most likely chord: {likely_chord}\n       (with {stats})")
                                log(f" --Recursively re-initialising {self.root.name}{naive_chord_name}/{bass.name} as {bass.name}{likely_chord.suffix}")
                                self.__init__(factors=likely_chord.factors, root=likely_chord.root, inversion=None)
                                return self._parse_inversion(0)
                            else:
                                log(f'Warning: Could not find a matching chord for {self.root.name}{naive_chord_name}/{bass.name}, closest match is {likely_chord} but not perfect')
                                self.__init__(factors=likely_chord.factors, root=likely_chord.root, inversion=None)
                                return self._parse_inversion(0)
                        except Exception as e:
                            raise Exception(f" Failed to re-initialise, uncaught error: {e}")

                else:
                    ### e.g. for D/C# case
                    log('     Throwing bass note on top of this chord and calling it an inversion')
                    new_intervals = IntervalList(list(self.root_intervals) + [bass_distance_from_root])
                assert new_intervals == new_intervals.sorted()
                print(f'    New intervals: {new_intervals}')
                # recursively re-initialise:
                self.__init__(intervals=new_intervals, root=self.root, bass=bass)
                return self._parse_inversion(bass.name)

            ####################################################################

            inversion_degree = [k for k,v in self.factor_notes.items() if v == bass][0]
            # get inversion from inversion_degree:
            for x, deg in enumerate(sorted(self.factors.keys())):
                if inversion_degree == deg:
                    inversion = x
                    break
            assert isinstance(inversion, int), f"Invalid inversion degree for this chord: {inversion}"

        # infer inverted note order by finding the bass's place in our root_notes notelist:
        # bass_place = [i for i, n in enumerate(self.root_notes) if n == bass][0]
        # assert inversion == bass_place ### is this always true?
        bass_place = inversion # kludge? odd behaviour around 11sus4 // 13sus4 // 13sus2 chords

        # and rearranging the notes by rotation, e.g. from ordering [0,1,2] to [1,2,0]:
        # inverted_notes = self.root_notes.rotate(bass_place)
        # inverted_intervals = [Interval(0)] + [n - bass for n in inverted_notes[1:]]
        inverted_intervals = self.root_intervals.invert(bass_place)
        inverted_notes = NoteList([bass + i for i in inverted_intervals])

        inv_params = (inversion, inversion_degree, bass)
        return (inv_params), inverted_notes, inverted_intervals

    @property
    def _inv_string(self):
        """inversion string, used internally by suffix method (and inherited by subclasses)"""
        return f'/{self.bass.name}' if (self.inversion != 0) else ''

    def _detect_sharp_preference(self, default=False): #tonic, quality='major', default=False):
        """detect if a chord should prefer sharp or flat labelling
        depending on its tonic and quality"""
        if self.quality.major:
            if self.root in sharp_major_tonics:
                return True
            elif self.root in flat_major_tonics:
                return False
            else:
                return default
        elif self.quality.minor:
            if self.root in sharp_minor_tonics:
                return True
            elif self.root in flat_minor_tonics:
                return False
            else:
                return default
        else:
            return default

    def _set_sharp_preference(self, prefer_sharps):
        """set the sharp preference of this Chord,
        and of all notes inside this Chord,
        including the tonic, root, and constituent factors"""
        if prefer_sharps is None:
            # detect from object attributes
            prefer_sharps = self._detect_sharp_preference()

        self.prefer_sharps = prefer_sharps
        self.root._set_sharp_preference(prefer_sharps)
        self.bass._set_sharp_preference(prefer_sharps)
        for n in self.notes:
            n._set_sharp_preference(prefer_sharps)

    @property
    def sharp_notes(self):
        """returns notes inside self, all with sharp preference"""
        return NoteList([Note(n.chroma, prefer_sharps=True) for n in self.notes])

    @property
    def flat_notes(self):
        """returns notes inside self, all with flat preference"""
        return NoteList([Note(n.chroma, prefer_sharps=False) for n in self.notes])

    @property
    def name(self):
        return f'{self.root.name}{self.suffix}'

    @property
    def short_name(self):
        # identical to self.name in the case of Chord class
        return f'{self.root.name}{self.suffix}'

    def __hash__(self):
        # chords hash based on their notes and intervals
        return hash((self.notes, self.intervals))

    @property
    def _marker(self):
        """unicode character marker identifying this class"""
        return '♬'

    @property
    def _brackets(self):
        # just use brackets of NoteList class:
        return self.notes._brackets

    def __str__(self):
        return f'{self._marker} {self.name}'

    def __repr__(self):
        lb, rb = self._brackets
        notes_str = [] # notes are annotated with accent marks depending on which octave they're in (with respect to root)
        for i, n in zip(self.intervals, self.notes):
            assert (self.bass + i) == n, f'bass ({self.bass}) + interval ({i}) should be {n}, but is {self.bass + i}'
            nl, na = str(n)[:2], str(n)[2:] # note letter and accidental (so we can put the dot over the letter)
            if i < -12:
                notes_str.append(f'{nl}\u0324{na}') # lower diaresis
            elif i < 0:
                notes_str.append(f'{nl}\u0323{na}') # lower dot
            elif i < 12:
                notes_str.append(str(n))
            elif i < 24:
                notes_str.append(f'{nl}\u0307{na}') # upper dot
            else:
                notes_str.append(f'{nl}\u0308{na}') # upper diaresis
        notes_str = ', '.join(notes_str)

        return f'{str(self)}  {lb}{notes_str}{rb}'

    # def __repr__(self):
    #     return str(self)

    def __contains__(self, item):
        """Chords can contain degrees (as integers), intervals (as Intervals),
        or notes (as Notes, or strings that cast to Notes)"""
        if isinstance(item, Interval):
             return item in self.intervals # note: uses inverted intervals, not root position
        elif isinstance(item, int):
            return item in self.factors
        elif isinstance(item, (Note, str)):
            n = Note(item)
            return n in self.notes
        else:
            raise TypeError(f'Chord object cannot contain items of type: {type(item)}')

    def __eq__(self, other):
        """Chords are equal to others on the basis of their root, factors and inversion"""
        if type(other) == Chord:
            return (self.factors == other.factors) and (self.inversion == other.inversion) and (self.root == other.root)
        else:
            raise TypeError(f'Chords can only be compared to other Chords')

    def __hash__(self):
        return hash(((tuple(self.factors.items())), self.inversion, self.root))

    # enharmonic equality:
    def enharmonic_to(self, other):
        """Compares enharmonic equivalence between Chords,
        i.e. whether they contain the exact same notes (but not necessarily in the same order),
        or between Chord and AbstractChord, i.e. do they contain the same intervals"""
        if isinstance(other, Chord):
            matching_notes = 0
            for note in self.notes:
                if note in other.notes:
                    matching_notes += 1
            if matching_notes == len(self.notes) and len(self.notes) == len(other.notes):
                return True
            else:
                return False
        elif isinstance(other, AbstractChord):
            return self.intervals == other.intervals
        else:
            raise TypeError(f'Enharmonic equivalence operator & not defined between Chord and: {type(other)}')

    # enharmonic comparison operator:
    def __and__(self, other):
        return self.enharmonic_to(other)


    ### relative majors/minors are not very well-defined for chords (as opposed to keys), but we can have them anyway:
    @property
    def relative_minor(self):
        # assert not self.minor, f'{self} is already minor, and therefore has no relative minor'
        assert self.quality.major, f'{self} is not major, and therefore has no relative minor'
        rel_root = relative_minors[self.root.name]
        new_factors = ChordFactors(self.factors)
        new_factors[3] -= 1 # flatten third
        if 5 in self.factors: # if fifth is aug/dim, make it dim/aug
            new_factors[5] = -self.factors[5]
        return Chord(factors=new_factors, root=rel_root, inversion=self.inversion)

    @property
    def relative_major(self):
        # assert not self.major, f'{self} is already major, and therefore has no relative major'
        assert self.quality.minor, f'{self} is not minor, and therefore has no relative major'
        rel_root = relative_majors[self.root.name]
        new_factors = ChordFactors(self.factors)
        new_factors[3] += 1 # raise third
        if 5 in self.factors: # if fifth is aug/dim, make it dim/aug
            new_factors[5] = -self.factors[5]
        return Chord(factors=new_factors, root=rel_root, inversion=self.inversion)

    @property
    def relative(self):
        if self.quality.major:
            return self.relative_minor
        elif self.quality.minor:
            return self.relative_major
        else:
            raise Exception(f'Chord {self} is neither major or minor, and therefore has no relative')

    @property
    def parallel_minor(self):
        if not self.quality.major_ish:
            raise Exception(f'{self} is not major, and therefore has no parallel minor')
        new_factors = ChordFactors(self.factors)
        new_factors[3] -= 1 # flatten third
        if 5 in self.factors: # if fifth is aug/dim, make it dim/aug
            new_factors[5] = -self.factors[5]
        return Chord(factors=new_factors, root=self.root, inversion=self.inversion)

    @property
    def parallel_major(self):
        if not self.quality.minor_ish:
            raise Exception(f'{self} is not minor, and therefore has no parallel major')
        new_factors = ChordFactors(self.factors)
        new_factors[3] += 1 # raise third
        if 5 in self.factors: # if fifth is aug/dim, make it dim/aug
            new_factors[5] = -self.factors[5]
        return Chord(factors=new_factors, root=self.root, inversion=self.inversion)

    @property
    def parallel(self):
        if self.quality.major:
            return self.parallel_minor
        elif self.quality.minor:
            return self.parallel_major
        else:
            raise Exception(f'Chord {self} is neither major or minor, and therefore has no parallel')

    def __neg__(self):
        """returns the parallel major or minor (using negation operator '-')"""
        return self.parallel

    def __invert__(self):
        """returns the relative major or minor (using inversion operator '~')"""
        return self.relative

    def invert(self, inversion=None, inversion_degree=None, bass=None):
        """returns a new Chord based off this one, but inverted.
        not to be confused with self.__invert__!"""
        return Chord(factors=self.factors, root=self.root, inversion=inversion, inversion_degree=inversion_degree, bass=bass)

    def abstract(self):
        """return the AbstractChord that this Chord is associated with"""
        return AbstractChord(factors=self.factors)

    def _get_flags(self):
        """Returns a list of the boolean flags associated with this object"""
        flags_names = {
                       'inversion': self.inversion,
                       'quality': self.quality,
                       'suspended': self.suspended,
                       'diminished': self.diminished,
                       'augmented': self.augmented,
                       'indeterminate': self.indeterminate,
                       'fifth chord': self.fifth_chord,
                       'extended': self.extended,

                       }
        return [string for string, attr in flags_names.items() if attr]

    #### useful properties:

    @property
    def properties(self):
        flags = ', '.join(self._get_flags())
        return f"""
        {str(self)}
        Type:           {type(self)}

        Name:           {self.name}
        Root:           {self.root}
        Intervals:      {self.intervals}
        Notes:          {self.notes}

        Factors:        {self.factors}
        Inversion:      {self.inversion}
          (bass note):  {self.bass}

        Suffix:         {self.suffix}
        Quality:        {self.quality}

        SharpPref:      {self.prefer_sharps}

        Flags:          {flags}
        ID:             {id(self)}"""

    def summary(self):
        print(self.properties)


    #### audio methods:

    # wrappers for the NoteList audio methods of self.notes:
    def _waves(self, *args, **kwargs):
        return self.notes._waves(*args, **kwargs)

    def _chord_wave(self, *args, **kwargs):
        return self.notes._chord_wave(*args, **kwargs)

    def _melody_wave(self, *args, **kwargs):
        return self.notes._melody_wave(*args, **kwargs)

    def play(self, *args, **kwargs):
        self.notes.play(*args, **kwargs)


################################################################################

##### attempt no2 at chord types/rarities:

chord_names_by_rarity = { 0: ['', 'm', '7', '5'],   # basic chords: major/minor triads, dom/minor 7s, and power chords
                          1: ['m7', 'maj7', 'dim', 'sus4', 'sus2', 'add9'], # maj/min7s, dim triads, and common alterations like sus2/4 and add9
                          2: ['mmaj7', 'dim7', 'hdim7', '6', 'm6', 'aug7', '9', 'maj9', 'm9', 'aug'], # sixths, mmaj/diminished 7ths, augs and common 9ths
                          3: ['7b5', '7#9', 'add4', '7b9', 'dim9', 'dmin9', 'mmaj9', 'hdmin9', 'dimM7', 'augM7'] + [f'{q}{d}' for q in ('', 'm', 'maj') for d in (11,13)],
                          4: ['add11', 'add13'] + [f'{q}{d}' for q in ('dim', 'mmaj') for d in (11,13)],
                          5: [], 6: [], 7: []}

# removed no5 - handled better by incomplete chord matching

ordered_modifier_names = ['sus4', 'sus2', 'add9', 'add11', 'add13']
modifier_names_by_rarity = {1: ['sus4', 'sus2'], 2: ['add9'], 3: ['add11'], 4: ['add13']}

# these modifiers make a chord's quality indeterminate, so we don't apply them to chords that have had the minor qualifier already applied
ind_modifiers = {'sus4', 'sus2', '5'}
# these chord names cannot be modified:
unmodifiable_chords = {'', '5', '(no5)', 'add4', 'add9', 'add11', 'add13'}
# '' because most ordinary chord types imply modification from major, i.e. 'sus4' implies ['' + 'sus4']
# '5' and '(no5)' because they both imply simple removals of triad degrees, and are best handled by fuzzy matching
# and add4/add9/add11 chords because they are themselves modifiers; they combine oddly with sus2/sus4, and must be done strictly in sus/add order

# now we'll loop over those chords and build a dict mapping intervals/factors to their names:
factors_to_chord_names, intervals_to_chord_names = {}, {}
# (while adding chord modifications/alterations as well)

chord_name_rarities = unpack_and_reverse_dict(chord_names_by_rarity)
modifier_name_rarities = unpack_and_reverse_dict(modifier_names_by_rarity)

new_rarities = {i: [] for i in range(8)}
for rarity, chord_names in chord_names_by_rarity.items():
    log(f'Handling base chords for rarity={rarity}, chords={chord_names}')

    for chord_name in chord_names:
        base_chord = AbstractChord(chord_name)
        log(f'Handling base chord: r:{rarity} {chord_name}')

        if base_chord.factors in factors_to_chord_names or base_chord.intervals in intervals_to_chord_names:
            log(f'  {chord_name} clash with {intervals_to_chord_names[base_chord.intervals]}')
        else:
            factors_to_chord_names[base_chord.factors] = chord_name
            intervals_to_chord_names[base_chord.intervals] = chord_name

# handle the modifiers of base chords in a new loop:
for rarity, chord_names in chord_names_by_rarity.items():
    log(f'Handling modifiers for rarity={rarity}, chords={chord_names}')

    for chord_name in chord_names:
        if chord_name not in unmodifiable_chords:
            base_chord = AbstractChord(chord_name)
            # now: add chord modifications to each base chord as well, increasing rarity accordingly
            for mod_name in ordered_modifier_names:
                modifier = qualities.chord_modifiers[mod_name] # fetch ChordQualifier object by name
                # add a modification if it does not already exist by name and is valid on this base chord:
                if modifier.valid_on(base_chord.factors):
                    # (we check if base chord is major because the modifiers on their own apply to major chords,
                    #  i.e. the chord 'sus2' implies ['' + 'sus2'])
                    if not ((modifier in ind_modifiers) and (base_chord.quality.minor)):
                        altered_name = chord_name + mod_name

                        altered_factors = base_chord.factors + modifier
                        altered_intervals = altered_factors.to_intervals()
                        # avoid double counting: e.g. this ensures that '9sus4' and 'm9sus4' are treated as one chord, '9sus4', despite both being a valid chord init
                        if altered_factors not in factors_to_chord_names and altered_intervals not in intervals_to_chord_names:
                            factors_to_chord_names[altered_factors] = altered_name
                            intervals_to_chord_names[altered_intervals] = altered_name

                            # figure out the rarity of this modification and add it to the rarity dict:
                            mod_rarity = modifier_name_rarities[mod_name]
                            altered_rarity = chord_name_rarities[chord_name] + mod_rarity
                            new_rarities[altered_rarity].append(altered_name)

                            # finally: do the same again, but one level deeper!
                            for mod_name2 in ordered_modifier_names:
                                modifier2 = qualities.chord_modifiers[mod_name] # fetch ChordQualifier object by name
                                # do not apply the same modifier twice, and do so only if valid:
                                if (modifier2 is not modifier) and modifier2.valid_on(altered_factors):
                                    if not ((modifier2 in ind_modifiers) and (base_chord.quality.minor)):
                                        # and, special case, not if (no5) is the first mod, since it always comes last:
                                        if mod_name != '(no5)':
                                            altered2_name = altered_name + mod2_name

                                            altered2_factors = altered_factors + modifier2
                                            altered2_intervals = altered2_factors.to_intervals()
                                            # avoid the lower triangular: (e.g. m(no5)add9 vs madd9(no5))
                                            if altered2_factors not in factors_to_chord_names and altered2_intervals not in intervals_to_chord_names:
                                                factors_to_chord_names[altered2_factors] = altered2_name
                                                intervals_to_chord_names[altered2_intervals] = altered2_name

                                                # these are all rarity 7, the 'legendary chords'
                                                new_rarities[7].append(altered2_name)

# update chord_names_by_rarity with new rarities:
for r, names in new_rarities.items():
    chord_names_by_rarity[r].extend(names)

# re-instantiate the reverse dict since we've added to the forward one (but we still needed it earlier:)
chord_name_rarities = unpack_and_reverse_dict(chord_names_by_rarity)

# reverse these too:
chord_names_to_factors = reverse_dict(factors_to_chord_names)
chord_names_to_intervals = reverse_dict(intervals_to_chord_names)

######################################################

######### function for matching likely chords from unordered lists of note names (e.g. guitar fingerings)
# we cannot use intervals for this, because notes being in an arbitrary order means that
# their relative intervals are much less informative ,so we really must initialise every imaginable chord

def matching_chords(note_list, display=True,
                    assume_root=True, require_root=True, invert=True,
                    upweight_third=True, downweight_fifth=True,
                    min_recall=0.8, min_precision=0.7, min_likelihood=0.5, max_results=8):
    """from an unordered set of notes, return a dict of candidate chords that could match those notes.
    we make no assumptions about the note list, except in the case of assume_root, where we slightly
    privilege chords that have their root on the same note as the starting note in note_list.
    alternatively, if invert is True, we invert candidate chords to match the note_list's starting note.

    if weight_third, we place more emphasis on the candidate chords' third degrees for prec/recall statistics."""
    try:
        note_list = NoteList(note_list)
    except Exception as e:
        print(f'{note_list} does not appear to be a valid list of notes')
        raise e

    candidates = {} # we'll build a list of Chord object candidates as we go
    # keying candidate chord objs to (rec, prec, likelihood, consonance) tuples

    # we'll try building notes starting on every unique note in the note_list
    # (this implicitly means that we require the tonic to be in the input, which is fine)
    unique_notes = note_list.unique()

    for n in unique_notes:
        for rarity, chord_names in chord_names_by_rarity.items():

            # (no5) is already a missing degree, so we don't search chords that include it:
            # names_to_try = [n for n in chord_names if '(no5)' not in n]
            names_to_try = chord_names

            for chord_name in names_to_try:
                # init chord more efficiently than by name:
                cand_factors = chord_names_to_factors[chord_name]
                candidate = Chord(factors=cand_factors, root=n)

                likelihood = candidate.likelihood # float from 0.3 to 1.0

                # if candidate doesn't share the 'root', we can invert it:
                if (candidate.root != note_list[0]):
                    if invert and (note_list[0] in candidate.notes):
                        candidate = candidate.invert(bass=note_list[0])
                        # or otherwise just assume the note_list's root and make the non-inversion slightly less likely:
                    elif assume_root:
                        likelihood -= 0.15 # increase rarity by one-and-a-half steps

                weights = {}
                # upweight the third if asked for:
                if (upweight_third) and (3 in candidate.factors):
                    weights[candidate.factor_notes[3]] = 2
                # only downweight perfect fifths:
                if (downweight_fifth) and (5 in candidate.factors) and (candidate.factor_intervals[5]==7):
                    weights[candidate.factor_notes[5]] = 0.5
                # if require root, we only accept chords that share the bass note with the note_list:
                if (not require_root) or (candidate.bass == note_list[0]):
                    precision, recall = precision_recall(unique_notes, candidate.notes, weights=weights)
                    consonance = candidate.consonance # float from ~0.4 to ~0.9, in principle

                    if recall >= min_recall and precision >= min_precision and likelihood >= min_likelihood:
                        candidates[candidate] = {   'recall': round(recall,    2),
                                                 'precision': round(precision, 2),
                                                'likelihood': round(likelihood,2),
                                                'consonance': round(consonance,3)}

    # return sorted candidates dict:
    sorted_cands = sorted(candidates,
                          key=lambda c: (candidates[c]['recall'],
                                         candidates[c]['precision'],
                                         candidates[c]['likelihood'],
                                         candidates[c]['consonance']),
                          reverse=True)[:max_results]

    if display:
        # print result as nice dataframe instead of returning a dict
        title = [f"Chord matches for notes: {note_list}"]
        if assume_root:
            title.append(f'(assumed root: {note_list[0].name})')
        if not invert:
            title.append('(inversions disallowed)')
        else:
            title.append('(inversions allowed)')

        title = ' '.join(title)
        print(title)

        # we'll figure out how long we need to make each 'column' by iterating through cands:
        chord_name_parts = []
        note_list_parts = []
        for cand in sorted_cands:
            # break chord string up for nice viewing:
            str_parts = str(cand).split(' ')
            chord_name_parts.append(' '.join(str_parts[:2]))
            note_list_parts.append(' '.join(str_parts[2:]))
        longest_name_len = max([len(str(s)) for s in (chord_name_parts + ['  chord name'])])+3
        longest_notes_len = max([len(str(s)) for s in (note_list_parts + ['    notes'])])+3

        left_header =f"{'  chord name':{longest_name_len}} {'    notes':{longest_notes_len}}"
        score_parts = ['recall', 'precision', 'lklihood', 'consonance']
        hspace = 8
        right_header = ' '.join([f'{h:{hspace}}' for h in score_parts])
        out_list = [left_header + right_header]

        combi_chars = {"\u0324", "\u0323", "\u0307", "\u0308"} # a kludge: we have to count combining characters separately for chord notelist formatting

        for i, cand in enumerate(sorted_cands):
            scores = candidates[cand]
            rec, prec, lik, cons = list(scores.values())
            name_str, notes_str = chord_name_parts[i], note_list_parts[i]
            num_combi_chars = len([c for c in notes_str if c in combi_chars])

            descriptor = f'{name_str:{longest_name_len}} {notes_str:{longest_notes_len + num_combi_chars}}'
            scores = f' {str(rec):{hspace}} {str(prec):{hspace}}  {str(lik):{hspace}}  {cons:.03f}'
            out_list.append(descriptor + scores)
        print('\n'.join(out_list))
    else:
        return {c: candidates[c] for c in sorted_cands}

def most_likely_chord(note_list, stats=False, **kwargs):
    """from an unordered set of notes, return the single most likely chord,
    within specified constraints, as a tuple of (Chord, match_params)"""

    # by default, relax all minimum score constraints (to ensure we get something rather than nothing)
    # but allow overwriting by kwarg
    for kwarg in ['min_precision', 'min_recall', 'min_likelihood']:
        if kwarg not in kwargs:
            kwargs[kwarg] = 0.0
    candidates = matching_chords(note_list, display=False, **kwargs)
    best_match = list(candidates.keys())[0]
    match_params = candidates[best_match]
    if stats:
        return best_match, match_params
    else:
        return best_match


### WIP, incomplete class
class ChordVoicing(Chord):
    """a Chord built on a specific note of a specific pitch, whose members are OctaveNotes.
    unlike its parent classes, a ChordVoicing can have repeats of the same Note at multiple pitches.

    exact same attributes as chord, except also having a self.octave attribute defined"""
    def __init__(self, name=None, root=None, octave=None, factors=None, intervals=None, inversion=None, qualifiers=None, in_key=None):

        self.root, self.octave, chord_name = self._parse_root_octave(name, root, octave)

        self.factors, self.intervals, self.inversion = self._parse_input(chord_name, factors, intervals, inversion, inversion_degree, qualifiers)

        ### TBI: everything else

    @staticmethod
    def _parse_root_octave(name, root, octave):
        """takes the class's name and root input args
        and returns an OctaveNote object as root, integer as octave,
        and string or None object as chord_name"""
        # parse root and octave:
        if name is not None:
            assert root is None, f"ChordVoicing initialised with name string ({name}) as root, but also received mutually exclusive root keyword: {root}"
            assert octave is not None, f"ChordVoicing initialised with name string ({name}) as root but no octave arg provided"
            root_name, chord_name = parsing.note_split(name)
            root = Note(root_name)
            if len(chord_name) == 0:
                chord_name = None
            return root, octave, chord_name
        else:
            if isinstance(root, OctaveNote):
                # if root is an OctaveNote, we accept that:
                root = root
                assert octave is None, f"ChordVoicing initialised with OctaveNote ({root}) as root but also received mutually exclusive octave keyword: {octave}"
                octave = root.octave
            elif isinstance(root, Note):
                assert octave is not None, f"ChordVoicing initialised with Note ({root}) as root but no octave arg provided"
                root = root.in_octave(octave)
                octave = octave
            elif isinstance(root, str):
                if root[-1].isnumeric():
                    # string that seems to be an OctaveNote
                    assert octave is None, f"ChordVoicing initialised with string denoting OctaveNote ({root}) but also received mutually exclusive octave keyword: {octave}"
                    root = OctaveNote(root)
                    octave = root.octave
                else:
                    assert octave is not None, f"ChordVoicing initialised with Note string ({root}) as root but no octave arg provided"
                    octave = octave
                    root = Note(root).in_octave(octave)
            return root, octave, name
