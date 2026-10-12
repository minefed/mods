/* Copyright (c) 2026 Minefed. SPDX-License-Identifier: MIT */
package team.minefed.bluemap;

import java.util.*;
import java.util.function.Predicate;

/** Dependency-free exhaustive checks; run with Java 17 and assertions are not required. */
public final class MultipartConditionsTest {
    public static void main(String[] args) {
        List<String> states = product(Map.of("east", List.of("none", "low", "tall"),
                "north", List.of("none", "low", "tall"), "up", List.of("false", "true"),
                "waterlogged", List.of("false", "true")));
        MultipartConditions.Converter converter = MultipartConditions.prepare(states);
        verify(states, converter, state -> true);
        verify(states, converter, state -> false);
        Map<String, Object> rectangle = verify(states, converter,
                state -> !state.get("north").equals("none") && state.get("up").equals("true"));
        require(rectangle.equals(Map.of("north", "low|tall", "up", "true")), "Rectangle was not reduced");
        verify(states, converter, state -> state.get("east").equals(state.get("north")));
        verify(states, converter, state -> state.get("up").equals("true") ||
                state.get("north").equals("none") && !state.get("east").equals("none"));
        Random random = new Random(352045L);
        for (int trial = 0; trial < 500; trial++) {
            BitSet selected = new BitSet(states.size());
            for (int row = 0; row < states.size(); row++) if (random.nextBoolean()) selected.set(row);
            Map<String, Object> condition = converter.condition(selected);
            for (int row = 0; row < states.size(); row++)
                require(matches(condition, parse(states.get(row))) == selected.get(row), "Random truth table differs");
        }
        // State order must not affect meaning, and property-free blocks have one valid state.
        Collections.shuffle(states, random);
        verify(states, MultipartConditions.prepare(states), state -> state.get("north").equals("low"));
        verify(List.of(""), MultipartConditions.prepare(List.of("")), state -> true);
        verify(List.of(""), MultipartConditions.prepare(List.of("")), state -> false);
        rejected(() -> MultipartConditions.prepare(List.of("a=x,b=x", "a=y,b=y")));
        rejected(() -> MultipartConditions.prepare(List.of("a=x", "a=x")));
        rejected(() -> MultipartConditions.prepare(List.of("a=x", "b=x")));
        rejected(() -> MultipartConditions.prepare(List.of("a=x,a=y")));
        rejected(() -> MultipartConditions.prepare(List.of("a=x|y")));
        rejected(() -> converter.condition(BitSet.valueOf(new long[]{1L << states.size()})));
        Map<String, List<String>> wallProperties = new TreeMap<>();
        for (String direction : List.of("east", "north", "northeast", "northwest", "south", "southeast", "southwest", "west"))
            wallProperties.put(direction, List.of("none", "low", "tall"));
        wallProperties.put("up", List.of("false", "true"));
        wallProperties.put("waterlogged", List.of("false", "true"));
        List<String> walls = product(wallProperties);
        require(walls.size() == 26244, "Expected all diagonal-wall states");
        MultipartConditions.Converter wallConverter = MultipartConditions.prepare(walls);
        verify(walls, wallConverter, state -> state.get("northwest").equals("tall"));
        verify(walls, wallConverter, state -> state.get("up").equals("true") ||
                state.get("east").equals("none") && state.get("west").equals("none") ||
                state.get("northeast").equals("low") && state.get("southwest").equals("tall"));
        System.out.println("MultipartConditionsTest passed: 500 random truth tables and all 26,244 diagonal-wall states");
    }

    private static Map<String, Object> verify(List<String> states, MultipartConditions.Converter converter,
                                              Predicate<Map<String, String>> predicate) {
        BitSet selected = new BitSet(states.size());
        for (int row = 0; row < states.size(); row++) if (predicate.test(parse(states.get(row)))) selected.set(row);
        Map<String, Object> condition = converter.condition(selected);
        for (int row = 0; row < states.size(); row++)
            require(matches(condition, parse(states.get(row))) == selected.get(row), "Truth table differs: " + condition);
        return condition;
    }

    private static List<String> product(Map<String, List<String>> properties) {
        List<String> states = new ArrayList<>(List.of(""));
        for (Map.Entry<String, List<String>> entry : new TreeMap<>(properties).entrySet()) {
            List<String> next = new ArrayList<>();
            for (String state : states) for (String value : entry.getValue())
                next.add(state + (state.isEmpty() ? "" : ",") + entry.getKey() + "=" + value);
            states = next;
        }
        return states;
    }

    private static Map<String, String> parse(String state) {
        Map<String, String> result = new HashMap<>();
        if (!state.isEmpty()) for (String pair : state.split(",")) {
            String[] split = pair.split("="); result.put(split[0], split[1]);
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private static boolean matches(Map<String, Object> condition, Map<String, String> state) {
        for (Map.Entry<String, Object> item : condition.entrySet()) {
            if (item.getKey().equals("OR")) {
                if (((List<Map<String, Object>>) item.getValue()).stream().noneMatch(child -> matches(child, state))) return false;
            } else if (item.getKey().equals("AND")) {
                if (((List<Map<String, Object>>) item.getValue()).stream().anyMatch(child -> !matches(child, state))) return false;
            } else if (!Arrays.asList(((String) item.getValue()).split("\\|")).contains(state.get(item.getKey()))) return false;
        }
        return true;
    }

    private static void rejected(Runnable action) {
        try { action.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Invalid input was accepted");
    }

    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
}
