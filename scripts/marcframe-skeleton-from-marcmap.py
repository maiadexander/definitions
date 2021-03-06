# -*- coding: UTF-8 -*-
from __future__ import unicode_literals, print_function
from collections import OrderedDict, namedtuple
import re
import json
import sys


MARC_TYPES = 'bib', 'auth', 'hold'

content_name_map = {
    'Books': 'Text',
    'Book': 'Text',
    'Maps': 'Cartography',
    'Map': 'Cartography',
    'Music': 'Audio',
    'Serials': 'Serial',
    'Computer': 'Digital'
}

carrier_name_map = {
    'ComputerFile': 'Electronic',
    'ProjectedGraphic': 'ProjectedImage',
    'NonprojectedGraphic': 'StillImage',
    'MotionPicture': 'MovingImage',
}

propname_map = {
    'iSSN': 'issn',

    'item': 'additionalCarrierType',
    'format': 'additionalType',
    'type': 'holdingType',

    'receipt': 'acquisitionStatus',
    'method': 'acquisitionMethod',
    'generalRetention': 'retentionPolicy',
    'policyType': 'specificRetentionPolicy',
    'numberUnits': 'retentionPolicyNumberOfUnits',
    'unitType': 'retentionPolicyUnitType',
    'reproduction': 'reproductionPolicy',
}

canonical_coll_id_map = {
    "ReproductionType": ["ComputerFileAspectType", "SoundAspectType", "MicroformAspectType", "MotionPicAspectType", "ProjGraphAspectType", "NonProjAspectType", "GlobeAspectType", "MapAspectType"],
    "AudienceType": ["ComputerAudienceType", "MusicAudienceType", "VisualAudienceType", "BooksAudienceType"],
    "FilmBaseType": ["MotionPicBaseType", "MicroformBaseType"],
    "ColorType": ["MapColorType", "GlobeColorType"],
    "HeadingType": ["HeadingSeriesType", "HeadingMainType", "HeadingSubjectType"],
    "IndexType": ["MapsIndexType", "BooksIndexType"],
    "ItemType": ["SerialsItemType", "VisualItemType", "MusicItemType", "MapsItemType", "MixedItemType"],
    "MediumType": ["MotionPicMediumType", "ProjGraphMediumType", "VideoMediumType"],
    "PolarityType": ["MicroformPosNegType", "MapPosNegType"],
    "MotionPicConfigurationOrVideoPlaybackType": ["MotionPicConfigurationType", "VideoPlaybackType"],
    "NonProjectedType": ["NonProjSecondaryType", "NonProjPrimaryType"],
    "ColorType": ["ProjGraphColorType", "NonProjColorType"],
    "ReproductionType": ["GlobeReproductionType", "MapReproductionType"],
    "ConferencePublicationType": ["SerialsConfPubType", "BooksConfPubType"],
    "GovernmentPublicationType": ["SerialsGovtPubType", "ComputerGovtPubType", "BooksGovtPubType", "VisualGovtPubType", "MapsGovtPubType"],
    "SoundType": ["ProjGraphSoundType", "MotionPicSoundType", "VideoSoundType"],
    "HoldingType": ["Type"],
    'AcquisitionStatusType': ['ReceiptType'],
    'AcquisitionMethodType': ['MethodType'],
    'RetentionPolicyType': ['GeneralRetentionType'],
    'SpecificRetentionPolicyType': ['PolicyType'],
    'RetentionPolicyUnitType': ['UnitType'],
    'ReproductionPolicyType': ['ReproductionType'],
}

enum_value_patches = {
    'Avtalspost': {'id': 'LicenseAgreementBoundDescription',
        'label_en': "License agreement bound description"},
    'Exemplarinformation': {'id': 'ItemInfoInRecord',
        'label_en': "Item info in record"},
    'Exemplarinformation_finns_ej': {'id': 'NoItemInfoInRecord',
        'label_en': "No item info in record"},
    'Löpande_katalogisering_-_Odefinierat': {'id': 'RunningCataloguingOrUndefined',
        'label_en': "Running cataloguing / Undefined"},
    'Pliktleverans': {'id': 'LegalDeposit',
        'label_en': "Legal deposit"},
    'Retrospektiv_katalogisering': {'id': 'RetrospectiveCataloguing',
        'label_en': "Retrospective cataloguing"},
    'Undertrycks_i_nyförvärvslista': {'id': 'SuppressedInNewAquisitionsList',
        'label_en': "Suppressed in new aquisitions list"},
    'Exakt_uppgift_om_bit-djup-siffror': {'id': 'BitDepth',
        'label_en': "Bit depth (in digits)"},
}


get_canonical_coll_id = {alias: key
    for key, aliases in canonical_coll_id_map.items()
        for alias in aliases}.get


fixprop_typerefs = {
    '000': [
        'typeOfRecord',
        'bibLevel',
    ],
    '007': [
        'mapMaterial',
        'computerMaterial',
        'globeMaterial',
        'tacMaterial',
        'projGraphMaterial',
        'microformMaterial',
        'nonProjMaterial',
        'motionPicMaterial',
        'kitMaterial',
        'notatedMusicMaterial',
        'remoteSensImageMaterial', #'soundKindOfMaterial',
        'soundMaterial',
        'textMaterial',
        'videoMaterial'
    ],
    '008': [
        'booksContents', #'booksItem', 'booksLiteraryForm' (subjectref), 'booksBiography',
        'computerTypeOfFile',
            #'mapsItem', #'mapsMaterial', # TODO: c.f. 007.mapMaterial
        #'mixedItem',
        #'musicItem', #'musicMatter', 'musicTransposition',
        'serialsTypeOfSerial', #'serialsItem',
        'visualMaterial', #'visualItem',
    ],
    '006': [
        'booksContents',
        'computerTypeOfFile',
        'serialsTypeOfSerial',
        'visualMaterial',
    ]
}
# TODO: literaryForm => genre (same as 655)


common_columns = {
    '008': {"[0:6]", "[6:7]", "[7:11]", "[11:15]", "[15:18]", "[35:38]", "[38:39]", "[39:40]"}
}


TOKEN_MAPS = OrderedDict()

ENUM_DEFS = OrderedDict()

#compositionTypeMap = OUT['compositionTypeMap'] = OrderedDict()
#contentTypeMap = OUT['contentTypeMap'] = OrderedDict()

EnumCollection = namedtuple('EnumCollection', 'ref_key, map_key, id, items, type, off_key')


PROCESSED_ENUMS = {}

def build_enums(marc_type):

    enum_map = PROCESSED_ENUMS[marc_type] = {}
    enum_collections = []

    for dfn_ref_key, valuemap in MARCMAP[marc_type]['fixprops'].items():
        enumcoll, tokenmap_key = _make_enumcollection(marc_type, dfn_ref_key, valuemap)
        enum_map[tokenmap_key] = enum_map[enumcoll.map_key] = enumcoll
        enum_collections.append((enumcoll, dfn_ref_key))

    for enumcoll, dfn_ref_key in enum_collections:

        if MAKE_VOCAB:
            coll_def = add_enum_collection_def(enumcoll)

        overwriting = enumcoll.map_key in TOKEN_MAPS
        #if enumcoll.map_key in TOKEN_MAPS: continue
        tokenmap = TOKEN_MAPS.setdefault(enumcoll.map_key, {})

        for key, dfn in enumcoll.items.items():
            enum_id = dfn['enum_id']

            if MAKE_VOCAB and enum_id:
                add_enum_def(enumcoll, enum_id, dfn_ref_key, dfn, key)

            if overwriting:
                assert tokenmap.get(key, enum_id) == enum_id, "%s: %s missing in %r" % (
                        key, enum_id, tokenmap)

            existing_enum_id = tokenmap.get(key, enum_id)
            if existing_enum_id is not None and existing_enum_id != enum_id:
                print("tokenMap mismatch in %s for key %s: %s != %s"
                        % (dfn_ref_key, key, enum_id, tokenmap[key]), file=sys.stderr)
            else:
                tokenmap[key] = enum_id


TMAP_HASHES = {} # to reuse repeated tokenmap

def _make_enumcollection(marc_type, dfn_ref_key, valuemap):
    items = filtered_enum_values(valuemap)
    tokenmap_key = marc_type + '-' + dfn_ref_key
    # reuse repeated tokenmaps
    canonical_tokenmap_key = TMAP_HASHES.setdefault(
            json.dumps(items, sort_keys=True), tokenmap_key)

    coll_id = _make_collection_id(dfn_ref_key)
    first_similar_coll_id = _make_collection_id(canonical_tokenmap_key.rsplit('-')[-1])

    canonical_coll_id = get_canonical_coll_id(coll_id)
    if canonical_coll_id:
        assert coll_id in canonical_coll_id_map[canonical_coll_id]
        assert first_similar_coll_id in canonical_coll_id_map[canonical_coll_id]
    else:
        canonical_coll_id = first_similar_coll_id

    if marc_type != 'bib' and 'bib-'+dfn_ref_key in TMAP_HASHES.values() and not canonical_tokenmap_key.startswith('bib-'):
        # NOTE: avoid conflating coll_def, prepend coll_id with 'Authority' or 'Holding'
        #print(canonical_tokenmap_key, tokenmap_key)
        pfx = {'auth': 'Authority', 'hold': 'Holding'}[marc_type]
        canonical_coll_id = pfx + canonical_coll_id
        coll_id = pfx + coll_id

    if canonical_tokenmap_key != tokenmap_key:
        #print("choosing {} over {}".format(canonical_tokenmap_key, tokenmap_key))
        if MAKE_VOCAB:
            for cid in [coll_id, first_similar_coll_id]:
                if cid == canonical_coll_id:
                    continue
                ENUM_DEFS.setdefault(canonical_coll_id, {"@id": canonical_coll_id}
                        ).setdefault('equivalentClass', []).append({"@id": cid})

    off_key = _find_boolean_off_key(items)
    # TODO: use key length to detect data properties (see is_link check far below)
    enumtype = None
    if off_key:
        enumtype = 'Boolean'
    elif all((v.get('id') or v.get('label_en', '')).isdigit()
            for k, v in valuemap.items() if k not in ('_', '|')):
        enumtype = 'Number'
        assert canonical_coll_id == 'NumberUnitsType'

    return EnumCollection(dfn_ref_key, canonical_tokenmap_key, canonical_coll_id, items,
            enumtype, off_key), tokenmap_key

def _make_collection_id(dfn_ref_key):
    coll_id = dfn_ref_key[0].upper() + dfn_ref_key[1:]
    if not coll_id.endswith('Type'):
        coll_id += 'Type'
    return coll_id

def filtered_enum_values(valuemap):
    def filtered():
        for k, v in valuemap.items():
            if fixed_enum_value(k, v):
                yield k.lower(), v
    return OrderedDict(sorted(filtered()))

def fixed_enum_value(key, dfn):

    if dfn.get('id') == 'TODO:value-in-digits':
        del dfn['id']

    if 'id' in dfn:
        # IMPROVE: move id generation from legacy config code to here...
        v = dfn['id']
        subname, plural_name = to_name(v)
    else:
        subname = dfn['label_sv']
        if ' [' in subname:
            subname, comment = subname.split(' [', 1)
            if comment[-1] == ']':
                comment = comment[:-1]

        for char, repl in [(' (', '-'), (' ', '_'), ('/', '-')]:
            subname = subname.replace(char, repl)
        for badchar in ',()':
            subname = subname.replace(badchar, '')

    if key in ('_', '|', '||', '|||') and any(t in subname
            for t in ('No', 'Ej', 'Inge', 'Uppgift_saknas')):
        #if key == '_':
        #    enum_id = 'Undefined'
        #else:
        return False

    elif subname.replace('Obsolete', '') in {
            'Unknown',
            #'Other',
            'NotApplicable',
            'Unspecified', 'Undefined'}:
        enum_id = None
        #enum_id = 'Unknown'
    else:
        if 'id' not in dfn and 'label_en' not in dfn:
            patch = enum_value_patches.get(subname)
            if patch:
                dfn.update(patch)
                subname = dfn['id']

        enum_id = subname

    if enum_id and enum_id.endswith('Obsolete') and len(enum_id) > 8 and enum_id[-9] not in ('/', '-'):
        enum_id = enum_id[:-8] + '-Obsolete'
        dfn['obsolete'] = True

    dfn['enum_id'] = enum_id
    return True

def _find_boolean_off_key(valuemap):
    if valuemap and len(valuemap) == 2:
        items = [(k, v['enum_id'].lower() if v['enum_id'] else '_')
                    for (k, v) in valuemap.items()]
        for off_index, (k, v) in enumerate(items):
            if v.startswith('no') or v.endswith('finns_ej'):
                on_k, on_v = items[not off_index]
                if True:# v.endswith(on_v.replace('present', '')):
                    #assert k == '0' and on_k == '1'
                    return k
                break

def to_name(name):
    name = name[0].upper() + name[1:]

    name = re.sub(r'(?<=[a-z])S(?=[A-Z])', 's', name) # SomeoneSName => SomeonesName

    #return name, None
    plural_name = None

    if 'And' in name:
        name_plural_pairs = [to_name(part) for part in name.split('And')]
        if name == 'CanonsAndRounds' or any(plural for name, plural in name_plural_pairs):
            return 'Or'.join(name for name, plural in name_plural_pairs), name
        else:
            return name, None

    if name == 'Theses':
        pural_name = name
        name = 'Thesis'
    elif name[0].isdigit() \
            or name.startswith(('Missing', 'Mixed', 'Multiple')) \
            or name.endswith(('Access', 'Atlas', 'Arms', 'Blues',
                'BubblesBlisters', 'Canvas', 'Characteristics', 'Contents',
                'ExceedsThreeCharacters', 'Glass', 'Lossless', 'Previous',
                'Series', 'Statistics', 'Thesaurus')):
        pass
    elif name.endswith('ies'):
        pural_name = name
        name = name[0:-3] + 'y'
    elif name in {'Indexes', 'LecturesSpeeches', 'Marches', 'Masses', 'Rushes',
                  'Speeches', 'Waltzes', }:
        pural_name = name
        name = name[0:-2]
    elif name.endswith('s'):
        plural_name = name
        name = name[0:-1]
    return name, plural_name


def add_enum_collection_def(enumcoll):
    coll_id = enumcoll.id
    #assert coll_id not in ENUM_DEFS, "Collection duplicate: %s" % coll_id
    coll_predef = ENUM_DEFS.get(coll_id)
    equiv_class = coll_predef['equivalentClass'] if coll_predef else []
    coll_def = ENUM_DEFS[coll_id] = {
        "@id": coll_id,
        "@type": ["CollectionClass"],
        "subClassOf": ["EnumeratedTerm"],
        #"inScheme": "",
        "notation": enumcoll.id, #enumcoll.map_key,
        "equivalentClass": equiv_class
        #"inRangeOf": propname
    }
    if enumcoll.type:
        coll_def['subClassOf'].append(enumcoll.type)
    return coll_def

def add_enum_def(enumcoll, enum_id, dfn_ref_key, dfn, key):
    #assert enum_id not in ENUM_DEFS
    assert enum_id != enumcoll.id, "Same as collection: %s" % enum_id

    ideal_enum_id = enum_id
    raw_id = "%s-%s" % (enumcoll.id, key)

    predef = ENUM_DEFS.get(enum_id)

    notation = predef['notation'] if predef else []
    if key not in notation:
        if notation:
            predef = None
            enum_id = raw_id
            notation = [key]
        else:
            notation.append(key)

    in_coll = predef['inCollection'] if predef else []
    if not any(r['@id'] == enumcoll.id for r in in_coll):
        in_coll.append({"@id": enumcoll.id})

    sameas = predef['sameAs'] if predef else []
    broader = predef['broader'] if predef else []
    broadmatch = predef['broadMatch'] if predef else []

    if enum_id == raw_id:
        broader.append({"@id": ideal_enum_id})
    else:
        sameas.append({"@id": raw_id})

    if key == enumcoll.off_key:
        broadmatch.append({'@id': 'sdo:False'})

    dest = ENUM_DEFS[enum_id] = {
        "@id": enum_id, "@type": in_coll,
        "sameAs": sameas,
        "broader": broader,
        "notation": notation,
        "inCollection": in_coll,
        "broadMatch": broadmatch,
    }
    add_labels(dfn, dest)
    if predef:
        for labelkey in 'prefLabel', 'prefLabel_en':
            dest[labelkey] = predef.get(labelkey, ()) + dest.get(labelkey, ())
    if dfn.get('obsolete'):
        dest['owl:deprecated'] = True


def add_labels(src, dest):
    sv = src.get('label_sv')
    en = src.get('label_en')
    #if sv or en:
    #    lang = dest['prefLabel'] = {}
    #    if sv: lang['sv'] = sv
    #    if en: lang['en'] = en
    if sv:
        dest['prefLabel'] = tuple(list(dest.get('prefLabel', [])) + [sv])
    if en:
        dest['prefLabel_en'] = tuple(list(dest.get('prefLabel_en', [])) + [en])


def process_marcmap(OUT, marc_type):
    section = OUT[marc_type] = OrderedDict()

    prevtag, outf = None, None
    for tag, field in sorted(MARCMAP[marc_type].items()):
        if not tag.isdigit():
            continue
        prevf, outf = outf, OrderedDict()
        section[tag] = outf
        subfields = field.get('subfield')
        subtypes = None
        if MAKE_VOCAB:
            outf['@type'] = 'skos:Collection'
            field_id = '%s-%s' % (marc_type, tag)
            outf['@id'] = field_id
            outf['notation'] = tag
            outf['marcType'] = marc_type

        fixmaps = field.get('fixmaps')
        if fixmaps:
            process_fixmaps(marc_type, tag, fixmaps, outf)

        elif not subfields:
            outf['addProperty'] = prep_propname(field['id'])

        else:
            for ind_key in ('ind1', 'ind2'):
                ind = field.get(ind_key)
                if not ind:
                    continue
                ind_keys = sorted(k for k in ind if k != '_')
                if ind_keys:
                    outf[ind_key.replace('ind', 'i')] = {}
            for code, subfield in subfields.items():
                code = code.lower()
                sid = subfield.get('id') or ""
                if sid.endswith('Obsolete'):
                    outf['obsolete'] = True
                    sid = sid[0:-8]
                if (code, sid) in [('6', 'linkage'), ('8', 'fieldLinkAndSequenceNumber')]:
                    continue
                subf = outf['$' + code] = OrderedDict()
                repeatable = subfield.get('repeatable', False)
                p_key = 'addProperty' if repeatable else 'property'
                if sid or not MAKE_VOCAB:
                    subf[p_key] = prep_propname(sid)
                if MAKE_VOCAB:
                    subf['@type'] = 'rdf:Property'
                    subf['@id'] = '%s-%s-%s' % (marc_type, tag, code)
                    subf['notation'] = code
                    subf['repeatable'] = repeatable
                    add_labels(subfield, subf)
            if len(outf.keys()) > 1 and outf == prevf:
                section[tag] = {'inherit': prevtag}
        if 'repeatable' in field:
            outf['repeatable'] = field['repeatable']
        if MAKE_VOCAB:
            add_labels(field, outf)
        prevtag = tag

    field_index = {}
    for tag, field in OUT[marc_type].items():
        if not any(k.startswith('$') for k in field):
            continue
        def hash_dict(d):
            return tuple((k, hash_dict(v) if isinstance(v, dict) else v)
                    for k, v in d.items())
        fieldhash = hash_dict(field)
        if fieldhash in field_index:
            field.clear()
            field['inherits'] = field_index[fieldhash]
        else:
            field_index[fieldhash] = tag


def process_fixmaps(marc_type, tag, fixmaps, outf):
    enum_map = PROCESSED_ENUMS[marc_type]
    tokenTypeMap = OrderedDict()

    for fixmap in fixmaps:
        #content_type = None
        orig_type_name = None
        type_name = None
        if len(fixmaps) > 1:
            if tag == '008':
                pass #rt_bl_map = outf.setdefault('recTypeBibLevelMap', OrderedDict())
            else:
                outf['addLink'] = 'hasFormat' if tag == '007' else 'hasPart'
                outf['[0]'] = {
                    'addProperty': '@type',
                    'tokenMap': tokenTypeMap,
                }
                outf['tokenTypeMap'] = '[0]'

            orig_type_name =  fixmap['name'].split(tag + '_')[1]
            type_name = fixmap.get('term') or orig_type_name
            if tag in ('006', '008'):
                type_name = content_name_map.get(type_name, type_name)
            elif tag in ('007'):
                type_name = carrier_name_map.get(type_name, type_name)

            fm = outf[type_name] = OrderedDict()
            if MAKE_VOCAB:
                fm['@type'] = 'owl:Class'
                add_labels(fixmap, fm)

            if tag == '008':
                pass
                #for combo in fixmap['matchRecTypeBibLevel']:
                #    rt_bl_map[combo] = type_name
                #    rt, bl = combo
                #    subtype_name = fixprop_to_name(fixprops, 'typeOfRecord', rt)
                #    if not subtype_name:
                #        continue
                #    comp_name = fixprop_to_name(fixprops, 'bibLevel', bl)
                #    if not comp_name:
                #        continue
                #
                #    #is_serial = type_name == 'Serial'
                #    #if comp_name == 'MonographItem' or is_serial:
                #    #    content_type = contentTypeMap.setdefault(type_name, OrderedDict())
                #    #    subtypes = content_type.setdefault('subclasses', OrderedDict())
                #    #    if is_serial:
                #    #        subtype_name += 'Serial'
                #    #    typedef = subtypes[subtype_name] = OrderedDict()
                #    #    typedef['typeOfRecord'] = rt
                #    #else:
                #    #    comp_type = compositionTypeMap.setdefault(comp_name, OrderedDict())
                #    #    comp_type['bibLevel'] = bl
                #    #    parts = comp_type.setdefault('partRange', set())
                #    #    parts.add(type_name)
                #    #    parts.add(subtype_name)

            else:
                for k in fixmap['matchKeys']:
                    tokenTypeMap[k] = type_name
        else:
            fm = outf

        real_fm = fm
        for col in fixmap['columns']:
            off, length = col['offset'], col['length']
            key = ('[%s]' % off if length == 1 else
                    '[%s-%s]' % (off, (off+length)-1))
            if key in common_columns.get(tag, ()):
                # IMPROVE: verify expected props?
                fm = outf
            else:
                fm = real_fm

            dfn_ref_key = col.get('propRef')
            if not dfn_ref_key:
                continue
            if orig_type_name == 'ComputerFile':
                orig_type_name = 'Computer'
            if orig_type_name and dfn_ref_key.title().startswith(orig_type_name):
                new_propname = dfn_ref_key[len(orig_type_name):]
                new_propname = new_propname[0].lower() + new_propname[1:]
                #print(new_propname, '<-', dfn_ref_key)
            else:
                new_propname = None

            fm[key] = col_dfn = OrderedDict()
            propname = new_propname or dfn_ref_key or col.get('propId')
            if propname in propname_map:
                propname = propname_map[propname]

            domainname = 'Record' if tag == '000' else None
            if dfn_ref_key in fixprop_typerefs.get(tag):
                if tag == '007':
                    propname = 'carrierType'
                    repeat = True
                elif tag in ('006', '008'):
                    propname = 'contentType'
                    repeat = True
            else:
                repeat = False

            if MAKE_VOCAB:
                add_labels(col, col_dfn)

            if domainname:
                col_dfn['domainEntity'] = domainname

            enumcoll = enum_map.get(marc_type + '-' + dfn_ref_key)

            is_link = length < 3 and not enumcoll or enumcoll and enumcoll.type != 'Number'
            if is_link:
                col_dfn['addLink' if repeat else 'link'] = prep_propname(propname)
                col_dfn['uriTemplate'] = "{_}"
            else:
                if propname or not MAKE_VOCAB:
                    col_dfn['addProperty' if repeat else 'property'] = prep_propname(propname)

            default = col.get('default')
            if default:
                col_dfn['default'] = default

            if enumcoll:

                # TODO: check type of tokenmap (boolean, numeric (or fixed like here))
                items = enumcoll.items.items()
                if len(items) == 1 and items[0][0] != 'u':
                    col_dfn['fixedDefault'] = items[0][0]

                if enumcoll.type:
                    col_dfn['valueType'] = enumcoll.type
                    if enumcoll.type == 'Boolean':
                        col_dfn['fixedDefault'] = enumcoll.off_key
                        col_dfn['valueMap'] = {k: k != enumcoll.off_key for k, v in items}

                if is_link:
                    col_dfn['tokenMap'] = enumcoll.id
                    col_dfn['uriTemplate'] = "marc:%s-{_}" % enumcoll.id
                else:
                    col_dfn['valuePattern'] = [k for k, v in items]

                if MAKE_VOCAB:
                    colpropid = '%s-%s-%s' % (marc_type, tag, key)
                    #if colpropid in ENUM_DEFS: print(colpropid)
                    prop_dfn = {'@id': propname, '@type': 'owl:ObjectProperty'}
                    ranges = [{'@id': enumcoll.id}]
                    if enumcoll.type:
                        ranges.append({'@id': enumcoll.type})
                    prop_dfn['sdo:rangeIncludes'] = ranges
                    add_labels(col, prop_dfn)
                    ENUM_DEFS[colpropid] = prop_dfn

                    coll_dfn = ENUM_DEFS[enumcoll.id]
                    add_labels(col, coll_dfn)
                    if type_name:
                        prop_dfn['sdo:domainIncludes'] = {'@id': 'v:' + type_name}
                        # NOTE: means "enumeration only applicable if type of
                        # thing linking to it is of this type"
                        coll_dfn.setdefault('broadMatch', []).append('v:' + type_name)

                    # TODO: represent broadMatch and
                    # domainIncludes+rangeIncludes combos as anonymous
                    # subproperties, like:
                    #   :contentType a owl:ObjectProperty;
                    #       :combinations [
                    #               :prefLabel "Type of Continuing Resource"@en;
                    #               rdfs:domain v:Serial; rdfs:range :SerialsTypeOfSerialType
                    #           ], [
                    #               :prefLabel "Type of Material"@en;
                    #               rdfs:domain v:Visual; rdfs:range :VisualMaterialType
                    #           ].


#def fixprop_to_name(fixprops, propname, key):
#    dfn = fixprops[propname].get(key)
#    if dfn and 'id' in dfn:
#        return to_name(dfn['id'])[0]
#    else:
#        return None


def prep_propname(propname):
    if not propname:
        return None
    return 'marc:%s' % propname


if __name__ == '__main__':
    args = sys.argv[1:]
    fpath = args.pop(0) if args else "legacy/marcmap.json"
    with open(fpath) as f:
        MARCMAP = json.load(f, object_pairs_hook=OrderedDict)

    ONLYENUMS = '--enums' in args
    MAKE_VOCAB = ONLYENUMS or '--vocab' in args

    OUT = OrderedDict()

    if MAKE_VOCAB:
        import string
        terms = {
            "@base": "https://id.kb.se/marc/",
            "v": "https://id.kb.se/vocab/", # TODO: kbv
            #"inCollection": {"@reverse": "skos:member"},
            "inCollection": None,
            "prefLabel": {"@id": "skos:prefLabel", "@language": "sv"},
            "prefLabel_en": {"@id": "prefLabel", "@language": "en"},
            "tokenMaps": None,
            "domain": {"@id": "rdfs:domain", "@type": "@vocab"},
            "range": {"@id": "rdfs:range", "@type": "@vocab"},
            "inRangeOf": {"@reverse": "rdfs:range", "@type": "@vocab"},
            "subClassOf": {"@id": "rdfs:subClassOf", "@type": "@vocab"},
            "broadMatch": {"@id": "skos:broadMatch", "@type": "@id"},
            "bib": None if ONLYENUMS else {"@id": "@graph", "@container": "@index"},
            "auth": None if ONLYENUMS else {"@id": "@graph", "@container": "@index"},
            "hold": None if ONLYENUMS else {"@id": "@graph", "@container": "@index"},
            'uriTemplate': None,
            #"tokenMap": None,
            "link": {"@id": "sameAs", "@type": "@vocab"},
            "addLink": {"@id": "sameAs", "@type": "@vocab"},
            "property": {"@id": "sameAs", "@type": "@vocab"},
            "addProperty": {"@id": "sameAs", "@type": "@vocab"},
            "inScheme": {"@type": "@id"},
            "marcType": {"@id": "inScheme", "@type": "@id"},
            "@vocab": "https://id.kb.se/marc/",
            #'i1': None,
            #'i2': None,
        }
        terms.update({'$' + k: 'skos:member' for k in string.digits + string.ascii_lowercase})
        OUT["@context"] = ["../sys/context/base.jsonld", terms]
        OUT['@graph'] = []
    #else:
    OUT['tokenMaps'] = None

    for marc_type in MARC_TYPES:
        build_enums(marc_type)

    for marc_type in MARC_TYPES:
        process_marcmap(OUT, marc_type)

    # cleanup
    for enum in ENUM_DEFS.values():
        for k, v in enum.items():
            if not v:
                del enum[k]
    if ENUM_DEFS:
        ENUM_DEFS['CollectionClass'] = {
            "@id": "CollectionClass", "@type": "owl:Class",
            "subClassOf": ["owl:Class", "skos:Collection"]
        }
        ENUM_DEFS['EnumeratedTerm'] = {
            "@id": "EnumeratedTerm", "@type": "owl:Class",
            "subClassOf": ["skos:Concept", "sdo:Enumeration"]
        }
        OUT['@graph'].append({"@id": "enums", "@graph": ENUM_DEFS.values()})

    #collids = {collkey: coll.id for k, v in PROCESSED_ENUMS.items() for collkey, coll in v.items()}
    #tmaps = OrderedDict(sorted((collids[tk],
    #            OrderedDict(sorted((k,
    #                    v.get('id') or v.get('label_sv') if isinstance(v, dict) else v)
    #                for k, v in tv.items())))
    #         for tk, tv in TOKEN_MAPS.items()))
    #OUT['tokenMaps'] = TOKEN_MAPS

    ## sanity check..
    #prevranges = None
    #for k, v in compositionTypeMap.items():
    #    ranges = v['partRange']
    #    if prevranges and ranges - prevranges:
    #        print("differs", k)
    #    else:
    #        assert any(r in contentTypeMap for r in ranges)
    #        v.pop('partRange')
    #    prevranges = ranges

    class SetEncoder(json.JSONEncoder):
        def default(self, obj):
            return list(obj) if isinstance(obj, set) else super(SetEncoder, self).default(obj)

    print(json.dumps(OUT,
            cls=SetEncoder,
            indent=2,
            ensure_ascii=False,
            separators=(',', ': ')
            ).encode('utf-8'))
