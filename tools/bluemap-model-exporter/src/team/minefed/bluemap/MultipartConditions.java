/* Copyright (c) 2026 Minefed. SPDX-License-Identifier: MIT */
package team.minefed.bluemap;

import java.util.*;

/** Converts a complete block-state truth table to exact vanilla multipart conditions. */
final class MultipartConditions {
    private static final Map<String, Object> TRUE = Map.of();
    private static final Map<String, Object> FALSE = Map.of("OR", List.of());

    static Converter prepare(List<String> serializedStates) {
        return new Converter(serializedStates);
    }

    static final class Converter {
        private final int stateCount;
        private final List<Property> properties = new ArrayList<>();

        Converter(List<String> serializedStates) {
            if (serializedStates.isEmpty()) throw new IllegalArgumentException("No block states");
            stateCount = serializedStates.size();
            List<SortedMap<String, String>> rows = new ArrayList<>(stateCount);
            Set<Map<String, String>> unique = new HashSet<>();
            SortedMap<String, SortedSet<String>> values = new TreeMap<>();
            for (String serialized : serializedStates) {
                SortedMap<String, String> row = parse(serialized);
                if (!rows.isEmpty() && !row.keySet().equals(rows.get(0).keySet()))
                    throw new IllegalArgumentException("Inconsistent block-state properties");
                if (!unique.add(row)) throw new IllegalArgumentException("Duplicate block state");
                rows.add(row);
                row.forEach((key, value) -> values.computeIfAbsent(key, ignored -> new TreeSet<>()).add(value));
            }
            long combinations = 1;
            for (Map.Entry<String, SortedSet<String>> entry : values.entrySet()) {
                combinations = Math.multiplyExact(combinations, entry.getValue().size());
                Property property = new Property(entry.getKey(), List.copyOf(entry.getValue()), stateCount);
                properties.add(property);
                for (int row = 0; row < rows.size(); row++) {
                    int value = Collections.binarySearch(property.values, rows.get(row).get(property.name));
                    property.masks[value].set(row);
                }
            }
            if (combinations != stateCount)
                throw new IllegalArgumentException("Block states must cover their full Cartesian product");
        }

        Map<String, Object> condition(BitSet matchingStates) {
            if (matchingStates.length() > stateCount)
                throw new IllegalArgumentException("Matching state index is out of bounds");
            return build((BitSet) matchingStates.clone(), 0);
        }

        private Map<String, Object> build(BitSet matching, int depth) {
            int count = matching.cardinality();
            if (count == 0) return FALSE;
            if (depth == properties.size()) return TRUE;

            // Most model selectors are one rectangle (e.g. north=low|tall).
            // Its projections contain exactly count combinations iff there are no holes.
            Map<String, Object> rectangle = new LinkedHashMap<>();
            long combinations = 1;
            for (int i = depth; i < properties.size(); i++) {
                Property property = properties.get(i);
                List<String> allowed = new ArrayList<>();
                for (int value = 0; value < property.values.size(); value++)
                    if (matching.intersects(property.masks[value])) allowed.add(property.values.get(value));
                combinations *= allowed.size();
                if (allowed.size() != property.values.size()) rectangle.put(property.name, String.join("|", allowed));
            }
            if (combinations == count) return rectangle;

            Property split = properties.get(depth);
            Map<Map<String, Object>, List<String>> groups = new LinkedHashMap<>();
            for (int value = 0; value < split.values.size(); value++) {
                BitSet branch = (BitSet) matching.clone();
                branch.and(split.masks[value]);
                if (branch.isEmpty()) continue;
                Map<String, Object> child = build(branch, depth + 1);
                groups.computeIfAbsent(child, ignored -> new ArrayList<>()).add(split.values.get(value));
            }
            List<Object> alternatives = new ArrayList<>();
            for (Map.Entry<Map<String, Object>, List<String>> group : groups.entrySet()) {
                Map<String, Object> child = group.getKey();
                if (group.getValue().size() == split.values.size()) {
                    alternatives.add(child);
                    continue;
                }
                Map<String, Object> selector = Map.of(split.name, String.join("|", group.getValue()));
                if (child.isEmpty()) alternatives.add(selector);
                else if (!child.containsKey("AND") && !child.containsKey("OR")) {
                    Map<String, Object> combined = new LinkedHashMap<>(selector);
                    combined.putAll(child);
                    alternatives.add(combined);
                } else alternatives.add(Map.of("AND", List.of(selector, child)));
            }
            if (alternatives.size() == 1) {
                @SuppressWarnings("unchecked") Map<String, Object> only = (Map<String, Object>) alternatives.get(0);
                return only;
            }
            return Map.of("OR", alternatives);
        }
    }

    private static SortedMap<String, String> parse(String serialized) {
        SortedMap<String, String> row = new TreeMap<>();
        if (serialized.isEmpty()) return row;
        for (String item : serialized.split(",", -1)) {
            int equals = item.indexOf('=');
            if (equals < 1 || equals == item.length() - 1 || item.indexOf('=', equals + 1) >= 0)
                throw new IllegalArgumentException("Invalid block-state property: " + item);
            String key = item.substring(0, equals), value = item.substring(equals + 1);
            if (key.equals("AND") || key.equals("OR") || value.contains("|"))
                throw new IllegalArgumentException("Reserved multipart syntax in property: " + item);
            if (row.put(key, value) != null) throw new IllegalArgumentException("Duplicate property: " + key);
        }
        return row;
    }

    private static final class Property {
        final String name;
        final List<String> values;
        final BitSet[] masks;
        Property(String name, List<String> values, int stateCount) {
            this.name = name;
            this.values = values;
            masks = new BitSet[values.size()];
            Arrays.setAll(masks, ignored -> new BitSet(stateCount));
        }
    }
}
