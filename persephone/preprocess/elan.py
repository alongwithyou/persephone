""" Provides a Corpus class that can read ELAN .eaf XML files. """

from pathlib import Path
from typing import List, Union

from pympi.Elan import Eaf

from .. import corpus
from ..utterance import Utterance

def utterances_from_eaf(eaf_path: Path, tiers: List[str]) -> None:#List[Utterance]:
    """
    Extracts utterances of the given tiers found in the ELAN .eaf XML file
    at eaf_path.
    """

    if not eaf_path.is_file():
        raise FileNotFoundError("Cannot find {}".format(eaf_path))

    def get_eaf_media_path(eafob: Eaf) -> Path:
        """ Determines the media_path of an object to use. """

        for md in eafob.media_descriptors:
            media_path = eaf_path.parent / md["RELATIVE_MEDIA_URL"]
            if media_path.is_file():
                return media_path

        # Sometimes the media file is in the same directory as the eaf
        # file, even if the eaf file says it's somewhere else.
        for md in eafob.media_descriptors:
            media_path = eaf_path.parent / Path(md["RELATIVE_MEDIA_URL"]).name
            if media_path.is_file():
                return media_path

        raise FileNotFoundError(
            """Cannot find media file corresponding to {}.
            Tried looking for the following files: {}.""".format(
                eaf_path, [md["RELATIVE_MEDIA_URL"]
                           for md in eafob.media_descriptors]))

    eaf = Eaf(str(eaf_path))
    media_path = get_eaf_media_path(eaf)
    print(media_path)

def elan_utterances(org_dir: Path, tiers: List[str]) -> List[Utterance]:
    """ Collects utterances from the ELAN *.eaf XML files found in a directory."""

    utterances = []
    for elan_path in good_elan_paths(org_dir=org_dir):
        eafob = Eaf(elan_path)
        #import pprint; pprint.pprint(dir(eafob))
        can_find_path = False
        for md in eafob.media_descriptors:
            try:
                media_path = os.path.join(os.path.dirname(elan_path),
                                          md["RELATIVE_MEDIA_URL"])
                if os.path.exists(media_path):
                    # Only one media_path file is needed, as long as it exists.
                    can_find_path = True
                    break
                # Try just looking for the basename specified in the
                # RELATIVE_MEDIA_URL
                media_path = os.path.join(os.path.dirname(elan_path),
                                          os.path.basename(md["RELATIVE_MEDIA_URL"]))
                if os.path.exists(media_path):
                    can_find_path = True
                    break
            except KeyError:
                # Then it might be hard to find the MEDIA URL if its not
                # relative. Keep trying.
                continue
        if can_find_path:
            tier_names = eafob.get_tier_names()
            for tier in tier_names:
                if tier.startswith("rf") or tier.startswith("xv") or tier in elan_tiers:
                    try:
                        participant = eafob.tiers[tier][2]["PARTICIPANT"]
                    except KeyError:
                        participant = None
                    for utterance_id, annotation in enumerate(
                            eafob.get_annotation_data_for_tier(tier)):
                        elan_prefix = os.path.splitext(
                            os.path.basename(elan_path))[0]
                        prefix = "{}.{}.{}".format(
                            elan_prefix, tier, utterance_id)
                        try:
                            start_time = annotation[0] + int(md["TIME_ORIGIN"])
                            end_time = annotation[1] + int(md["TIME_ORIGIN"])
                        except KeyError:
                            # Then TIME_ORIGIN wasn't specified, so we use the
                            # offsets as they are.
                            start_time = annotation[0]
                            end_time = annotation[1]
                        text = annotation[2]
                        utterance = Utterance(media_path, elan_path,
                                              prefix, start_time, end_time,
                                              text, participant)
                        if not utterance.text.strip() == "":
                            utterances.append(utterance)
        else:
            # TODO Make this an actual warning or do some sort of exception
            # handling
            print("Warning: Can't find the media file for {}".format(elan_path))

    return utterances

class Corpus(corpus.Corpus):
    def __init__(self, tgt_dir, feat_type="fbank", label_type="phonemes",
                 label_segmenter=None):#character_segmenter):
        """
        Need to think about this constructor. Ideally it should take a
        function:

            label_preprocess(utter: String) -> String

        which takes a unpreprocessed utterance (perhaps with spaces delimiting
        words in some orthography), and outputs a string where spaces delimit
        things like phonemes and tones.

        corpus.Corpus and corpus.ReadyCorpus could also take such an argument.

        There's probably also going to need to be a way for such a function to
        mark utterances so that they aren't included in the corpus. For
        example, for filtering out code-switched sentences.

        Currently the corpus.Corpus superclass takes a labels argument which is
        just a collection of phonemes etc which the corpus assumes have already
        been segmented correctly, so that it doesn't have to read the whole
        corpus to figure them out. corpus.Corpus should also have the option of
        taking the label_preprocess argument, in which case it would not take
        labels.

        This constructor, elan.Corpus, shouldn't be taking a labels
        argument, since ELAN files are unlikely ever going to
        phoneme-segmented and we don't really want to encourage linguists to do that
        and add tiers or anything. There could be a function that takes labels
        and produces a label_preprocess function that is based on the greedy
        left-to-right phoneme segmentation. So one would do:

            > labels = {"a", "x", "b", ..., etc}
            > greedy_segmenter = create_greedy_segmenter(labels)
            > corp = elan.Corpus(tgt_dir, label_preprocess=greedy_segmenter,
                                 feat_type="fbank", label_type="phonemes")

        I notice now that this means that label_type and label_preprocess needs
        to be manually coordinated by the creater of the elan.Corpus. Ideally 
        the label_preprocess function would dictate the label_type somehow.

        From the end user's perspective, what happens if the orthography cannot
        be automatically segmented with the greedy algorithm AND the user
        doesn't want to do character-level prediction AND they can't write
        their own segmentation algorithm because of lack of technical
        expertise. Then I guess that is a situation where they might want to
        do manual segmentation as it's the only option. In such cases, they
        should be able to create another ELAN tier as is and there can be a
        label_segmenter that is just the identity function.
        """

        # Read utterances from tgt_dir/elan/. Perhaps an org_dir for elan
        # utterances? I'm wary of mixing directories of input data and output
        # data because it needs to be easy to do a complete reset by just
        # deleting the directory.

        # utterances = self.read_elan_utterances()

        # Filter utterances based on some criteria (such as codeswitching).
        # Should this filter_for_some_reason function be an argument to the
        # constructor, or should it somehow be rolled into the segmenter? Could
        # have another function that takes a filter and a segmenter and a list
        # of utterances and returns another list of utterances.

        # tokenized_utterances = filter_for_some_reason(utterances)

        # segmented_utters = [label_segmenter(utter) for utter in tokenized_utterances]

        # Writes the utterances to the tgt_dir/label/ dir
        # self.write_labels(tokenized_utterances)

        # Extracts utterance level WAV information from the input file.
        # self.split_wavs(tokenized_utterances)

        # If we're being fed a segment_labels function rather than the actual
        # labels, then we do actually have to determine all the labels by
        # reading the utterances. A natural way around this is to make the
        # label_segmenter an immutable class (say, a NamedTuple) which stores
        # the labels etc.

        # labels = determine_labels(utterances)

        super().__init__(feat_type, label_type, tgt_dir, labels)
