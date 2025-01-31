from .qualities import Quality #, Major, Minor, Perfect, Augmented, Diminished
from .parsing import degree_names, num_suffixes, offset_accidentals
from .util import rotate_list, least_common_multiple, euclidean_gcd
from .conversion import value_to_pitch
import math

class Interval:
    """a signed distance between notes, defined in semitones and degrees (whole-tones).
    infers degree from semitone distance automatically,
    but degree can be specified explicitly to infer an
    augmented or diminished interval etc."""

    def __init__(self, value:int, degree=None):
        if isinstance(value, Interval):
            # accept re-casting from another interval object:
            if degree is None:
                degree = value.extended_degree
            # changed this to let degree kwarg overwrite init by interval
            value = value.value

        self.value = value # signed integer semitone distance

        # value is directional, but width is absolute:
        self.width = abs(value)

        # compound intervals span more than an octave:
        self.compound = (self.width >= 12)

        # whole-octave width, and interval width-within-octave (both strictly positive)
        self.octave_span, self.mod = divmod(self.width, 12)

        # intervals are directional, so even though degree is strictly-positive we store the sign here:
        self.sign = -1 if self.value < 0 else 1 # technically "non-negative" rather than "sign"
        self.ascending = (self.sign == 1)
        self.descending = (self.sign == -1)
        self.unison = (self.mod == 0)

        if degree is None:
            # no degree provided, so auto-detect degree by assuming ordinary diatonic intervals:
            self.degree = default_interval_degrees[self.mod] # * self.sign

            # self.extended_degree is >=8 if this is a ninth or eleventh etc,
            # but self.degree is always mod-7,
            # and both are strictly positive
            self.extended_degree = (self.degree + (7*self.octave_span))

        else:
            assert degree > 0, "Interval degree must be non-negative"

            # degree has been provided; we validate it here
            default_degree = (default_interval_degrees[self.mod] + (7*self.octave_span)) #* self.sign
            self.extended_degree = degree # * self.sign
            self.degree = (self.extended_degree - (7*self.octave_span)) #  * self.sign
            if self.unison:
                assert self.degree == 1, 'Degree of a unison (mod12) interval can never be anything but 1'
                assert ((self.extended_degree -1) % 7) == 0, 'Extended degree of a unison (mod12) interval must (-1) mod to 0'
            assert 0 < self.degree < 8
            # should not be more than 1 away from the default:
            degree_distance_from_default = abs(degree - default_degree)

            if degree_distance_from_default <= 2:
                # all good - interval fits to the desired degree
                pass
                # self.extended_degree = abs(degree) * self.sign
                # self.degree = (abs(self.extended_degree) - (7*self.octave_span)) * self.sign
            elif degree_distance_from_default in {8,9,10}:
                # interval has been asked to correspond to a degree one octave higher or lower than default
                # maybe this is fine fine: we can quietly re-init?
                raise ValueError(f'Interval init specified that interval of semitone distance {self.value}' +
                f' should correspond to degree={degree}, but that appears to be an octave up or down from default degree: {default_degree}')

            else:
                raise ValueError(f'Interval init specified that interval of semitone distance {self.value}' +
                f' should correspond to degree={degree}, but that is too far from default degree: {default_degree}')

        # determine this interval's quality:
        self.quality = self._detect_quality()

    def _detect_quality(self):
        """uses mod-value and mod-degree to determine the quality of this interval"""

        default_value = default_degree_intervals[self.degree]
        offset = (self.mod - default_value)

        if self.degree in perfect_degrees:
            quality = Quality.from_offset_wrt_perfect(offset)
        else: # non-perfect degree, major by default
            quality = Quality.from_offset_wrt_major(offset)
        return quality

    @property
    def ratio(self):
        if self.value in interval_ratios:
            return interval_ratios[self.value]
        else:
            # this is an extended interval that we don't have a just ratio for,
            # but we can say it's just the ratio of its mod, with the left side
            # raised by 2 to the power of the octave span
            left, right = interval_ratios[self.mod]
            left *= (2**self.octave_span)
            # reduce to simple form:
            gcd = euclidean_gcd(left, right)
            return (left // gcd, right // gcd)

    @property
    def consonance(self):
        """consonance of an interval, defined as
        the base2 log of the least common multiple of
        the sides of that interval's ratio"""
        l, r = self.ratio
        # calculate least common multiple of simple form:
        lcm = least_common_multiple(l,r)
        # log2 of that multiple:
        dissonance = math.log(lcm, 2)
        # this ends up as a number that ranges from 0 (for perfect unison)
        # to just under 15, (for the 7-octave compound minor second, of width 85)

        # so we invert it into a consonance between 0-1:
        return (15 - dissonance) / 15


    @staticmethod
    def from_degree(degree, quality=None, offset=None):
        """alternative init method: given a degree (and an optional quality)
        initialise the appropriate Interval object.
        degree is assumed to be appropriately major/perfect if not specified"""

        extended_degree = degree
        if degree >= 8:
            octave_span, degree = divmod(degree - 1, 7)
            degree += 1
        else:
            octave_span = 0

        if quality is not None:
            assert offset is None, f'Interval.from_degree received mutually exclusive quality and offset args'
            # cast to quality object if it is not one:
            quality = Quality(quality)
            if degree in perfect_degrees:
                offset = quality.offset_wrt_perfect
            else:
                offset = quality.offset_wrt_major
        elif offset is not None:
            assert quality is None, f'Interval.from_degree received mutually exclusive quality and offset args'
        else:
            # neither quality nor offset given: assume major/perfect, with no offset
            offset = 0

        default_value = default_degree_intervals[degree] + (12*octave_span)
        interval_value = default_value + offset
        return Interval(interval_value, degree=extended_degree)

    @property
    def offset_from_default(self):
        """how many semitones this interval is from its default/canonical (perfect/major) degree"""
        perfect_degree = self.degree in {1,4,5}
        offset = self.quality.offset_wrt_perfect if perfect_degree else self.quality.offset_wrt_major
        return offset
        # return self.offset_from_default_degree(self.degree)

    def offset_from_degree(self, degree):
        """how many semitones this interval is from some chosen (perfect/major) degree"""
        assert degree > 0
        deg_oct, mod_degree = (divmod(degree-1, 7))
        mod_degree += 1
        default_value = default_degree_intervals[mod_degree] + (12*deg_oct)
        offset = self.width - default_value
        return offset

    def __int__(self):
        return self.value

    # interval constructor methods:
    def __add__(self, other):
        # if isinstance(other, Interval):
        #     operand = other.value
        # elif isinstance(other, int):
        #     operand = other

        if isinstance(other, (int, Interval)):
            new_value = self.value + int(other)
            # result = Interval(new_value)
            # catch special case: addition/subtraction by octaves preserves this interval's degree/quality,
            # (except if there's been a sign change)
            if (self.mod == 0):
                # (but don't worry about it for addition/subtraction of unisons themselves)
                return Interval.from_cache(new_value)
            elif int(other) % 12 == 0:
                octave_of_addition = int(other) // 12
                # new_degree = ((((self.sign * self.extended_degree) + octave_of_addition) - 1) % 7) + 1
                new_sign = -1 if new_value < 0 else 1
                # invert the degree if there's been a sign change
                new_degree = self.degree if (new_sign == self.sign) else (9-self.degree)
                new_ext_degree = new_degree + (7*(abs(new_value) // 12))
                #
                # # new degree is an octave less if there's been a sign change:
                # new_sign = -1 if new_value < 0 else 1
                # if new_sign != self.sign:
                #     new_degree -= 7

                result = Interval(new_value, new_ext_degree)
            else:
                # return cached interval if it exists:
                result = Interval.from_cache(new_value)
            return result
        # elif isinstance(other, int):
        #     # cast to interval and call again recursively:
        #     return Interval(self.value + other)
        else:
            raise TypeError('Intervals can only be added to integers or other Intervals')

    def __radd__(self, other):
        # if isinstance(other, (int, Interval)):
        return self + other
        # else:
        #     return other + self

    def __sub__(self, other):
        if isinstance(other, (int, Interval)):
            # call __add__ method recursively:
            return self + (-other)
        #     return Interval(self.value - other.value)
        # elif isinstance(other, int):
        #     return Interval(self.value - other)
        else:
            raise TypeError('Intervals can only be subtracted from integers or other Intervals')

    def __mod__(self, m):
        """performs modulo on self.value and returns resulting interval"""
        return Interval.from_cache(self.value % m)

    def __neg__(self):
        if self.value == 0:
            return self
        else:
            return Interval(-self.value, self.extended_degree)

    def __invert__(self):
        """returns the inverted interval, which is distinct from the negative interval.
        negative of Interval(7) (perfect fifth) is Interval(-7) (perfect fifth descending),
        but the inverse, ~Interval(7) is equal to Interval(-5) (perfect fourth descending)"""
        new_mod = (-(12-self.mod)) * self.sign
        # stretch to higher octave if necessary:
        new_value = new_mod + (12 * self.octave_span)* -(self.sign)
        new_degree = (9-self.degree) + (7*self.octave_span) # * self.sign
        # new_degree = new_degree + (7 * self.octave_span) # * -(self.sign)
        # new_degree =


        return Interval(new_value, new_degree)

    def __abs__(self):
        if self.value > 0:
            return self
        else:
            return Interval(-self.value)

    def flatten(self):
        """returns Interval object corresponding to this interval's mod-value and mod-degree"""
        if self.value < 0:
            # invert before flattening:
            return (~self).flatten()
        else:
            return Interval(self.mod, degree=self.degree)

    def __eq__(self, other):
        """Value equivalence comparison for intervals - returns True if both have
        same value (but disregard degree)"""
        if isinstance(other, Interval):
            return self.value == other.value
        elif isinstance(other, int):
            return self.value == other
        else:
            raise TypeError('Intervals can only be compared to integers or other Intervals')


    def __and__(self, other):
        """Enharmonic equivalence comparison for intervals - returns True if both have
        same mod attr (but disregard degree and signed distance value)"""
        if isinstance(other, Interval):
            return self.mod == other.mod
        elif isinstance(other, int):
            return self.mod == (other % 12)
        else:
            raise TypeError('Intervals can only be compared to integers or other Intervals')

    def __ge__(self, other):
        if isinstance(other, Interval):
            return self.value >= other.value
        elif isinstance(other, int):
            return self.value >= other
        else:
            raise TypeError('Intervals can only be compared to integers or other Intervals')

    def __le__(self, other):
        return other >= self

    def __lt__(self, other):
        if isinstance(other, Interval):
            return self.value < other.value
        elif isinstance(other, int):
            return self.value < other
        else:
            raise TypeError('Intervals can only be compared to integers or other Intervals')

    def __gt__(self, other):
        return other < self

    def __int__(self):
        return self.value

    def __rsub__(self, other):
        return other - self.value

    def __hash__(self):
        """intervals only hash their values, not their degrees"""
        return hash(self.value)

    @property
    def name(self):
        if self.extended_degree in degree_names:
            # interval degree is at most a thirteenth:
            degree_name = degree_names[self.extended_degree]
            call_compound = False
        else:
            # greater than a thirteenth, so we just call it an extended whatever:
            degree_name = degree_names[self.degree]
            call_compound = True

        qualifiers = []
        if self.descending:
            qualifiers.append('descending')
        if call_compound:
            qualifiers.append('compound')

        if len(qualifiers) > 0:
            qualifier_string = ", ".join(qualifiers)
            qualifier_string = f' ({qualifier_string})'
        else:
            qualifier_string = ''

        return f'{self.quality.full_name.capitalize()} {degree_name.capitalize()}{qualifier_string}'

    @property
    def short_name(self):
        lb, rb = self._brackets
        if self.value == 0:
            return '‹Rt›'
        else:
            sign_str = '-' if self.sign == -1 else ''
            short_deg = f'{self.extended_degree}'
            return f'{lb}{sign_str}{self.quality.short_name}{short_deg}{rb}'


    # alternate str method:
    @property
    def factor_name(self):
        # display this interval as an accidental and a degree:
        acc = offset_accidentals[self.offset_from_default][0]
        sign_str = '' if self.sign == 1 else '-'
        return f'{sign_str}{acc}{self.extended_degree}'

    @property
    def _brackets(self):
        return '‹', '›'

    def __str__(self):
        lb, rb = self._brackets
        return f'{lb}{self.value}:{self.name}{rb}'

    def __repr__(self):
        return str(self)

    @staticmethod
    def from_cache(value):
        # return a cached Interval object with this value if it exists,
        # otherwise initialise a new one
        if value in cached_intervals:
            return cached_intervals[value]
        else:
            return Interval(value)

class IntervalList(list):
    """List subclass that is instantianted with an iterable of Interval-like objects and forces them all to Interval type".
    useful for representing the attributes of e.g. AbstractChords and Scales."""
    def __init__(self, *items):
        if len(items) == 1 and isinstance(items[0], (list, tuple)):
            # been passed a list of items, instead of a series of list items
            items = items[0]
        interval_items = self._cast_intervals(items)

        super().__init__(interval_items)
        self.value_set = set([s.value for s in self]) # for efficient use of __contains__

    @staticmethod
    def _cast_intervals(items):
        interval_items = []
        for item in items:
            if isinstance(item, Interval):
                # add note
                interval_items.append(item)
            elif isinstance(item, int):
                # cast int to interval (using cache if it exists)
                interval_items.append(Interval.from_cache(item))
            else:
                raise Exception('IntervalList can only be initialised with Intervals, or ints that cast to Intervals')
        return interval_items

    @property
    def _brackets(self):
        return '𝄁', ' 𝄁'

    def __str__(self):
        lb, rb = self._brackets
        return f'{rb}{", ".join([i.short_name for i in self])}{rb}'

    # # alternative str method:
    # def as_factors(self):
    #     """returns this list's intervals represented as numeric degree factors instead of quality-intervals"""
    #     lb, rb = self._brackets
    #     return f'{lb}{", ".join([i.factor_name for i in self])}{rb}'

    def __repr__(self):
        return str(self)

    @property
    def as_factors(self):
        # alternate string method, reports raised/lowered factor integers instead of major/minor/perfect degrees
        return [iv.factor_name for iv in self]

    def __add__(self, other):
        """adds a scalar to each interval in this list,
        or accepts an iterable and performs point-wise addition."""
        if isinstance(other, (int, Interval)):
            return IntervalList([i + other for i in self])
        elif isinstance(other, (list, tuple)):
            assert len(other) == len(self), f'IntervalLists can only be added with scalars or with other iterables of the same length'
            return IntervalList([i + j for i,j in zip(self, other)])
        else:
            raise TypeError(f'IntervalLists can only be added with ints, Intervals, or iterables of either, but got type: {type(other)}')

    def __iadd__(self, other):
        """add in place"""
        if isinstance(other, (int, Interval)):
            for i in self:
                i += other
            return self
        elif isinstance(other, (list, tuple)):
            assert len(other) == len(self), f'IntervalLists can only be added with scalars or with other iterables of the same length'
            for i,j in zip(self, other):
                i += j
            return self
        else:
            raise TypeError(f'IntervalLists can only be added with ints, Intervals, or iterables of either, but got type: {type(other)}')

    def __sub__(self, other):
        """subtracts a scalar from each interval in this list,
        or accepts an iterable of scalars and performs point-wise subtraction."""
        # if isinstance(other, (int, Interval)):
        #     return IntervalList([i - other for i in self])
        # elif isinstance(other, (list, tuple)):
        #     assert len(other) == len(self), f'IntervalLists can only be subtracted with scalars or with other iterables of the same length'
        #     return IntervalList([i - j for i,j in zip(self, other)])
        # else:
        #     raise TypeError(f'IntervalLists can only be subtracted with ints, Intervals, or iterables of either, but got type: {type(other)}')
        return self + (-other)

    def __isub__(self, other):
        self += (-other)
        return self

    def __neg__(self):
        """pointwise negation"""
        return IntervalList([-i for i in self])

    def __abs__(self):
        """returns a new IntervalList where any negative intervals are inverted to be positive"""
        return IntervalList([~i if i < 0 else i for i in self])

    def __hash__(self):
        """IntervalLists hash as sorted tuples for the purposes of chord/key reidentification"""
        return hash(tuple(self.sorted()))

    def __contains__(self, item):
        """check if interval with a value (not degree) of item is contained inside this IntervalList,
        using self.value_set for efficient lookup"""
        if isinstance(item, Interval):
            item = item.value
        return item in self.value_set

    def append(self, item):
        """as list.append, but updates our set object as well"""
        super().append(item)
        self.value_set = set([s.value for s in self])

    def remove(self, item):
        super().remove(item)
        self.value_set = set([s.value for s in self])

    def pop(self, item):
        popped_item = self[-1]
        del self[-1]
        self.value_set = set([s.value for s in self])

    def unique(self):
        """returns a new IntervalList, where repeated notes are dropped after the first"""
        unique_intervals = []
        unique_intervals_set = set() # for efficiency
        for i in self:
             if i not in unique_intervals_set:
                 unique_intervals.append(i)
                 unique_intervals_set.add(i)
        return IntervalList(unique_intervals)

    def sort(self):
        super().sort()

    def sorted(self):
        # note that sorted(IntervalList) returns a list, NOT an IntervalList.
        # we must use this instead
        return IntervalList(sorted(self))

    def strip(self):
        """remove unison intervals from start and end of this list"""
        if self[0].mod == 0:
            new_intervals = self[1:]
        else:
            new_intervals = self[:]
        if self[-1].mod == 0:
            new_intervals = new_intervals[:-1]
        return IntervalList(new_intervals)

    def pad(self, left=True, right=False):
        """if this list does NOT start and/or end with unisons, add them where appropriate"""
        assert self == self.sorted(), f'non-sorted IntervalLists should NOT be padded'
        if (self[0].mod != 0) and left:
            new_intervals = [Interval(0)] + self[:]
        else:
            new_intervals = self[:]
        if (self[-1].mod != 0) and right:
            # add unison/octave above the last interval:
            octave_span = self[-1].octave_span + 1
            new_intervals = new_intervals + [Interval(12*(octave_span))]
        return IntervalList(new_intervals)

    def flatten(self, duplicates=False):
        """flatten all intervals in this list and return them as a new (sorted) list.
        if duplicates=False, remove those that are non-unique. else, keep them. """
        new_intervals = [i.flatten() for i in self]
        if not duplicates:
            new_intervals = list(set(new_intervals))
        return IntervalList(sorted(new_intervals))

    def rotate(self, num_places):
        """returns the rotated IntervalList that begins num_steps up
        from the beginning of this one. used for inversions."""
        return IntervalList(rotate_list(self, num_places))

    def invert(self, position):
        """used for calculating inversions: rotates, then subtracts
        the value of the resulting first interval in list, and returns
        those inverted intervals as a new IntervalList"""
        rotated = self.rotate(position)
        recentred = rotated - rotated[0] # centres first interval to be root again
        positive = abs(recentred) # inverts any negative intervals to their positive inversions
        inverted = positive.unique().sorted()
        # inverted = recentred.flatten()   # inverts negative intervals to their correct values
        # inverted = IntervalList(list(set([~i if i < 0 else i for i in recentred]))).sorted()
        return inverted

    def stack(self):
        """equivalent to cumsum: returns a new IntervalList based on the successive
        sums of this one, as intervals from tonic.
        e.g. [M3, m3, M3, M3].stack() returns [M3, P5, M7, m10]"""
        interval_stack = self[:1]
        for i in self[1:]:
            interval_stack.append(i + interval_stack[-1])
        return IntervalList(interval_stack)

    def unstack(self):
        """inverse operation - assume we are already stacked as intervals from tonic,
        and recover the original stacked intervals.
        e.g. [M3, P5, M7, m10].unstack() returns [M3, m3, M3, M3]"""
        assert self == self.sorted(), f'Cannot unstack an un-ordered IntervalList: {self}'
        interval_unstack = self[:1]
        for i in range(1, len(self)):
            interval_unstack.append(self[i] - self[i-1])
        return IntervalList(interval_unstack)

# quality-of-life alias:
Intervals = IntervalList

# # from a list of intervals-from-tonic (e.g. a key specification), get the corresponding stacked intervals:
# def stacked_intervals(tonic_intervals):
#     stack = [tonic_intervals[0]]
#     steps_traversed = 0
#     for i, interval in enumerate(tonic_intervals[1:]):
#         prev_interval_value = stack[-1].value
#         next_interval_value = interval.value - prev_interval_value- steps_traversed
#         steps_traversed += prev_interval_value
#         stack.append(Interval(next_interval_value))
#     return stack
# # opposite operation: from a list of stacked intervals, get the intervals-from-tonic:
# def intervals_from_tonic(interval_stack):
#     tonic_intervals = [interval_stack[0]]
#     for i in interval_stack[1:]:
#         tonic_intervals.append(tonic_intervals[-1] + i)
#     return tonic_intervals

# which intervals are considered perfect/major:
perfect_intervals = {0, 5, 7}
major_intervals = {2, 4, 9, 11}
# minor_intervals = [1, 3, 8, 10]

# which degrees are considered perfect:
perfect_degrees = {1, 4, 5}

# how many whole tones does each semitone interval correspond to (by default):
default_interval_degrees = {
                0: 1,          # e.g. unison (0 semitones) is degree 1
                1:2, 2:2,      # seconds (1 or 2 semitones) are degree 2, etc.
                3:3, 4:3,
                5:4,
                6:5,           # by convention: dim5 is more common than aug4
                7:5,
                8:6, 9:6,
                10:7, 11:7,
                }

# and the reverse mapping
default_degree_intervals = {
                1: 0, # unison
                2: 2, # maj2
                3: 4, # maj3
                4: 5, # per4
                5: 7, # per5
                6: 9, # maj6
                7: 11, # maj7
                # 8: 12, # octave
                }





# interval aliases:

Unison = PerfectFirst = Perfect1st = Perfect1 = Per1 = Per1st = P1 = Rt = Interval(0)

MinorSecond = MinSecond = Minor2nd = Minor2 = Min2 = Min2nd = m2 = Interval(1)
MajorSecond = MajSecond = Major2nd = Major2 = Maj2 = Maj2nd = M2 = Interval(2)

DiminishedThird = DimThird = Diminished3rd = Dim3rd = Dim3 = d3 = Interval(2, degree=3)
MinorThird = MinThird = Minor3rd = Minor3 = Min3 = Min3rd = m3 = Interval(3)
MajorThird = MajThird = Major3rd = Major3 = Maj3 = Maj3rd = M3 = Interval(4)
AugmentedThird = AugThird = Augmented3rd = Aug3rd = Aug3 = A3 = Interval(5, degree=3)

DiminishedFourth = DimFourth = Diminished4th = Dim4th = Dim4 = d4 = Interval(4, degree=4)
PerfectFourth = PerFourth = Perfect4th = Perfect4 = Fourth = Per4 = Per4th = P4 = Interval(5)
AugmentedFourth = AugFourth = Augmented4th = Aug4th = Aug4 = A4 = Interval(6, degree=4)

DiminishedFifth = DimFifth = Diminished5th = Dim5th = Dim5 = d5 = Interval(6, degree=5)
PerfectFifth = PerFifth = Perfect5th = Perfect5 = Fifth = Per5 = Per5th = P5 = Interval(7)
AugmentedFifth = AugFifth = Augmented5th = Aug5th = Aug5 = A5 = Interval(8, degree=5)

DiminishedSixth = DimSixth = Diminished6th = Dim6th = Dim6 = d6 = Interval(7, degree=6)
MinorSixth = MinSixth = Minor6th = Minor6 = Min6 = Min6th = m6 = Interval(8)
MajorSixth = MajSixth = Major6th = Major6 = Maj6 = Maj6th = M6 = Interval(9)
AugmentedSixth = AugSixth = Augmented6th = Aug6th = Aug6 = A6 = Interval(10, degree=6)

DiminishedSeventh = DimSeventh = Diminished7th = Dim7th = Dim7 = d7 = Interval(9, degree=7)
MinorSeventh = MinSeventh = Minor7th = Minor7 = Min7 = Min7th = m7 = Interval(10)
MajorSeventh = MajSeventh = Major7th = Major7 = Maj7 = Maj7th = M7 = Interval(11)

Octave = Eightth = PerfectEightth = PerEightth = Perfect8th = Per8 = Per8th = P8 = Interval(12)

# compound seconds
MinorNinth = MinNinth = Minor9th = Minor9 = Min9 = Min9th = m9 = Interval(13)
MajorNinth = MajNinth = Major9th = Major9 = Maj9 = Maj9th = M9 = Interval(14)
AugmentedNinth = AugNinth = Augmented9th = Aug9th = Aug9 = Interval(15, degree=9)

# compound thirds
DiminishedTenth = DimTenth = Diminished10th = Dim10th = Dim10 = d10 = Interval(14, degree=10)
MinorTenth = MinTenth = Minor10th = Minor10 = Min10 = Min10th = m10 = Interval(15)
MajorTenth = MajTenth = Major10th = Major10 = Maj10 = Maj10th = M10 = Interval(16)
AugmentedTenth = AugTenth = Augmented10th = Aug10th = Aug10 = A10 = Interval(17, degree=10)

# compound fourths
DiminishedEleventh = DimEleventh = Diminished11th = Dim11th = Dim11 = d11 = Interval(16, degree=11)
PerfectEleventh = PerEleventh = Perfect11th = Perfect11 = Per11 = P11 = Interval(17)
AugmentedEleventh = AugEleventh = Augmented11th = Aug11th = Aug11 = A11 = Interval(18, degree=11)

# compound fifths
DiminishedTwelfth = DimTwelfth = Diminished12th = Dim12th = Dim12 = d12 = Interval(18, degree=12)
PerfectTwelfth = PerTwelfth = Perfect12th = Perfect12 = Per12 = P12 = Interval(19)
AugmentedTwelfth = AugTwelfth = Augmented12th = Aug12th = Aug12 = A12 = Interval(20, degree=12)

# compound sixths
DiminishedThirteenth = DimThirteenth = Diminished13th = Dim13th = Dim13 = d13 = Interval(19, degree=13)
MinorThirteenth = MinThirteenth = Minor13th = Minor13 = Min13 = Min13th = m13 = Interval(20)
MajorThirteenth = MajThirteenth = Major13th = Major13 = Maj13 = Maj13th = M13 = Interval(21)
AugmentedThirteenth = AugThirteenth = Augmented13th = Aug13th = Aug13 = A13 = Interval(22, degree=13)

common_intervals = [P1, m2, M2, m3, M3, P4, d5, P5, m6, M6, m7, M7, P8, m9, M9, m10, M10, P11, P12, m13, M13]
# cache common intervals by semitone value for efficiency:
cached_intervals = {c.value: c for c in common_intervals}

# interval whole-number ratios according to five-limit tuning just intonation:
interval_ratios = {0: (1,1),  1: (16,15),  2: (9,8),    3: (6,5),
                   4: (5,4),  5: (4,3),    6: (25,18),  7: (3,2),
                   8: (8,5),  9: (5,3),   10: (16,9),  11: (15,8),
                   12: (2,1)}



# # calculate ratios of extended intervals:
# higher_ratios = {}
# for higher_octave in range(1,4):
#     for i, (l,r) in interval_ratios.items():
#         # raise the left side of the ratio by an octave:
#         hi, hl = i+(12*higher_octave), l*(2*higher_octave)
#         # reduce to least common factors:
#         for factor in range(10,1,-1):
#             if (hl % factor == 0) and (r % factor == 0):
#                 higher_ratios[hi] = (hl // factor), (r // factor)
#                 print(f'above {i}:{l,r}, {hi}:{hl,r} is divisible by factor {factor}, produces {higher_ratios[hi]}')
#                 break
#         if hi not in higher_ratios:
#             print(f'above {i}:{l,r}, {hi}:{hl,r} not divisible by any factors')
#             higher_ratios[hi] = (hl, r)

# interval_ratios.update(higher_ratios)





# def consonance(i):
#     """consonance of an interval, defined as
#     the base2 log of the least common multiple of
#     the sides of that interval's ratio"""
#     l, r = self.ratio
#     # reduce ratio:
#     # gcd = euclidean_gcd(l,r)
#     # l, r = l // gcd, r // gcd
#     # calculate least common multiple of simple form:
#     lcm = least_common_multiple(l,r)
#     return math.log(lcm, 2)
